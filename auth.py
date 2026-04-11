"""
Enpro Filtration Mastermind — Authentication.

Email + password login, bcrypt hashing, signed session cookie (itsdangerous, 7-day).
Designed for the pilot: small, hand-seeded user list, no self-signup.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import User, is_ready as db_ready, session_factory

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "fm_session"
SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Pilot pin — shared across all seeded users. Override via env GLOBAL_PIN.
# Accept common short forms ("000", "0000") for the same default so voice-
# dictated logins work either way.
GLOBAL_PIN = os.environ.get("GLOBAL_PIN", "000")
_ACCEPTED_PINS = {GLOBAL_PIN, GLOBAL_PIN.rstrip("0") + "0" * max(0, 4 - len(GLOBAL_PIN))}
# Pilot user list — auto-seeded on startup if missing.
PILOT_USERS = [
    # Existing 4 pilot users — no rep_id, generic V2.11 catalog experience
    {"email": "peter.wilson@conveyance365.com", "name": "Peter Wilson", "rep_id": None},
    {"email": "andrew@conveyance365.com", "name": "Andrew Taylor", "rep_id": None},
    {"email": "grant_cook@enproinc.com", "name": "Grant Cook", "rep_id": None},
    {"email": "john_burnett@enproinc.com", "name": "John Burnett", "rep_id": None},
    # V2.12 test profiles — pre-mapped to real rep_ids from the customer
    # intel data so Peter can validate the per-rep customer context layer
    # without touching the production pilot accounts.
    {"email": "test.morec@enpro.local", "name": "Test Rep — MOREC00", "rep_id": "MOREC00"},
    {"email": "test.ambrb@enpro.local", "name": "Test Rep — AMBRB00", "rep_id": "AMBRB00"},
]

_SECRET = os.environ.get("SESSION_SECRET", "")
_serializer: Optional[URLSafeTimedSerializer] = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        if not _SECRET:
            raise RuntimeError("SESSION_SECRET env var not set")
        _serializer = URLSafeTimedSerializer(_SECRET, salt="fm-session-v1")
    return _serializer


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session cookie
# ---------------------------------------------------------------------------

def issue_session(user_id: int) -> str:
    return _get_serializer().dumps({"uid": user_id, "iat": int(datetime.utcnow().timestamp())})


def read_session(token: str) -> Optional[int]:
    try:
        data = _get_serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        return int(data.get("uid"))
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> User:
    """FastAPI dependency: returns the logged-in User or raises 401.

    Works with or without a live Postgres. When the DB is not ready, this
    returns a lightweight in-memory User object built from PILOT_USERS so the
    pilot can keep running against Cosmos-only deployments.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = read_session(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Session expired")
    if db_ready():
        async with session_factory()() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise HTTPException(status_code=401, detail="User not found")
            return user
    # In-memory fallback
    u = _resolve_pilot_user(user_id)
    if u is None:
        raise HTTPException(status_code=401, detail="User not found")
    return u


async def get_current_user_optional(request: Request) -> Optional[User]:
    """Soft variant — returns None instead of raising."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = read_session(token)
    if user_id is None:
        return None
    if db_ready():
        try:
            async with session_factory()() as session:
                return await session.get(User, user_id)
        except Exception as e:
            logger.warning(f"get_current_user_optional DB read failed: {e}")
    return _resolve_pilot_user(user_id)


def _resolve_pilot_user(user_id: int) -> Optional[User]:
    """Build an in-memory User from PILOT_USERS at index (user_id - 1)."""
    idx = user_id - 1
    if idx < 0 or idx >= len(PILOT_USERS):
        return None
    u = PILOT_USERS[idx]
    stub = User()
    stub.id = user_id
    stub.email = u["email"]
    stub.name = u["name"]
    stub.rep_id = u.get("rep_id")
    return stub


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: int
    pin: str = Field(min_length=1, max_length=20)


class LoginResponse(BaseModel):
    id: int
    email: str
    name: str


class UserOption(BaseModel):
    id: int
    name: str


@router.get("/users", response_model=list[UserOption])
async def list_users():
    """Public — pilot user dropdown for login screen."""
    if db_ready():
        try:
            async with session_factory()() as session:
                result = await session.execute(select(User).order_by(User.id))
                return [UserOption(id=u.id, name=u.name) for u in result.scalars().all()]
        except Exception as e:
            logger.warning(f"list_users DB read failed, falling back to PILOT_USERS: {e}")
    # In-memory fallback: Peter, Andrew, Grant, John (first 4 pilot users).
    # Stable 1-indexed IDs so session cookies survive process restarts.
    return [UserOption(id=i + 1, name=u["name"]) for i, u in enumerate(PILOT_USERS[:4])]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response):
    if req.pin not in _ACCEPTED_PINS:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    if db_ready():
        try:
            async with session_factory()() as session:
                user = await session.get(User, req.user_id)
                if user is None:
                    raise HTTPException(status_code=401, detail="Invalid user")
                token = issue_session(user.id)
                set_session_cookie(response, token)
                return LoginResponse(id=user.id, email=user.email, name=user.name)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"login DB read failed, falling back to PILOT_USERS: {e}")

    # In-memory fallback
    idx = req.user_id - 1
    if idx < 0 or idx >= len(PILOT_USERS):
        raise HTTPException(status_code=401, detail="Invalid user")
    u = PILOT_USERS[idx]
    token = issue_session(req.user_id)
    set_session_cookie(response, token)
    return LoginResponse(id=req.user_id, email=u["email"], name=u["name"])


async def seed_pilot_users(session: AsyncSession) -> int:
    """Insert any pilot users that don't already exist. Returns count inserted.

    rep_id is set on first insert only — manual SQL changes to existing users
    are preserved across deploys (no clobber)."""
    inserted = 0
    pin_hash = hash_password(GLOBAL_PIN)
    for u in PILOT_USERS:
        existing = (await session.execute(
            select(User).where(User.email == u["email"])
        )).scalar_one_or_none()
        if existing is None:
            session.add(User(
                email=u["email"],
                name=u["name"],
                password_hash=pin_hash,
                rep_id=u.get("rep_id"),
            ))
            inserted += 1
    if inserted:
        await session.commit()
    return inserted


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=LoginResponse)
async def me(user: User = Depends(get_current_user)):
    return LoginResponse(id=user.id, email=user.email, name=user.name)
