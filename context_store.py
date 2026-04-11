"""
Context Store — session-scoped cache for pregame context objects.

In-memory dict with TTL. Keyed by session_id. Stores the full output of
the pregame pipeline (knowledge + candidates + 8 parallel reasoning
results + gatekeeper check) so Turn 2+ hits can return pre-computed
answers in milliseconds instead of re-reasoning.

Pattern: Peter's v2.13 Voice Echo principle + Edge Crew v3 crowdsource.
"""

import time
import threading
from typing import Any, Optional

_TTL_SECONDS = 3600  # 1 hour per session context

_lock = threading.Lock()
_store: dict[str, dict[str, Any]] = {}


def set_context(session_id: str, context: dict[str, Any]) -> None:
    """Save a pregame context object for a session."""
    if not session_id:
        return
    with _lock:
        _store[session_id] = {
            "data": context,
            "expires_at": time.time() + _TTL_SECONDS,
        }


def get_context(session_id: str) -> Optional[dict[str, Any]]:
    """Retrieve a pregame context object, or None if missing/expired."""
    if not session_id:
        return None
    with _lock:
        entry = _store.get(session_id)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del _store[session_id]
            return None
        return entry["data"]


def clear_context(session_id: str) -> None:
    """Drop a session's context (e.g., on New Chat)."""
    with _lock:
        _store.pop(session_id, None)


def evict_expired() -> int:
    """Remove all expired entries. Returns count removed."""
    removed = 0
    now = time.time()
    with _lock:
        for sid in list(_store.keys()):
            if now > _store[sid]["expires_at"]:
                del _store[sid]
                removed += 1
    return removed


def stats() -> dict[str, int]:
    """Return cache stats for monitoring."""
    with _lock:
        return {"sessions": len(_store)}
