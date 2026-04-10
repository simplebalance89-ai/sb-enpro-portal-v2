"""
Enpro Filtration Mastermind — Cosmos DB conversation memory.

Replaces Postgres-based conversation_memory.py with Azure Cosmos DB (serverless).
Stores last 7 days of conversation history per session with automatic TTL cleanup.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("enpro.conversation_memory_cosmos")

RETENTION_DAYS = 7
TTL_SECONDS = RETENTION_DAYS * 86400  # 604800 seconds = 7 days
MAX_HISTORY_MESSAGES = 30
MAX_CONTENT_CHARS = 8000

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "https://enpro-sessions.documents.azure.com:443/")
COSMOS_KEY = os.environ.get("COSMOS_KEY", "")
COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE", "enpro-fm")
COSMOS_CONTAINER = "conversations"

_container = None

# In-memory cache for last recommended parts per session (fixes race condition)
# When Turn 1 saves parts, they're cached here immediately.
# Turn 2's resolve_coreference reads from cache first, Cosmos second.
_session_parts_cache: dict = {}  # {session_id: {"parts": [...], "timestamp": float}}


def _get_container():
    """Get or create the Cosmos DB container client."""
    global _container
    if _container:
        return _container

    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        logger.warning("Cosmos DB not configured — conversation memory disabled")
        return None

    from azure.cosmos import CosmosClient, PartitionKey

    client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)

    # Create database if not exists
    database = client.create_database_if_not_exists(id=COSMOS_DATABASE)

    # Create container with TTL enabled and session_id as partition key
    _container = database.create_container_if_not_exists(
        id=COSMOS_CONTAINER,
        partition_key=PartitionKey(path="/session_id"),
        default_ttl=TTL_SECONDS,
    )
    logger.info(f"Cosmos DB connected: {COSMOS_DATABASE}/{COSMOS_CONTAINER}")
    return _container


def _truncate(content: str) -> str:
    if len(content) <= MAX_CONTENT_CHARS:
        return content
    return content[:MAX_CONTENT_CHARS] + "...[truncated]"


def _turn_hash(session_id: str, role: str, content: str) -> str:
    """Idempotency key bucketed by minute."""
    bucket = int(datetime.now(timezone.utc).timestamp() // 60)
    raw = f"{session_id}|{role}|{content}|{bucket}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def append_message(
    session_id: str,
    role: str,
    content: str,
    products: Optional[List[Any]] = None,
) -> None:
    """Append a single message to Cosmos DB."""
    container = _get_container()
    if not container:
        return

    if role not in ("user", "assistant"):
        raise ValueError(f"invalid role: {role}")
    if not content:
        return

    truncated = _truncate(content)
    turn_id = _turn_hash(session_id, role, truncated)
    now = datetime.now(timezone.utc)

    doc = {
        "id": turn_id,
        "session_id": session_id,
        "role": role,
        "content": truncated,
        "created_at": now.isoformat(),
        "ttl": TTL_SECONDS,
    }
    if products:
        doc["products_json"] = products
        # Extract part numbers for coreference resolution
        recommended = []
        for p in products:
            if isinstance(p, dict):
                pn = p.get("Part_Number") or p.get("part_number") or p.get("Alt_Code") or ""
                if pn:
                    recommended.append(str(pn).strip())
        if recommended:
            doc["recommended_parts"] = recommended
            # Cache immediately for race condition fix
            import time
            _session_parts_cache[session_id] = {
                "parts": recommended,
                "product_data": products,  # Full product objects for compare
                "timestamp": time.time(),
            }
            logger.info(f"Cached {len(recommended)} parts + product data for session {session_id[:12]}...")

    try:
        container.upsert_item(doc)
    except Exception as e:
        logger.error(f"Cosmos append failed: {e}")


async def append_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    products: Optional[List[Any]] = None,
) -> None:
    """Append a user+assistant pair."""
    await append_message(session_id, "user", user_message)
    await append_message(session_id, "assistant", assistant_message, products=products)


async def get_recent_history(
    session_id: str,
    max_messages: int = MAX_HISTORY_MESSAGES,
) -> List[Dict]:
    """Return recent history as OpenAI chat messages, oldest first."""
    container = _get_container()
    if not container:
        return []

    query = (
        "SELECT c.role, c.content, c.created_at, c.products_json, c.recommended_parts "
        "FROM c WHERE c.session_id = @sid "
        "ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
    )
    params = [
        {"name": "@sid", "value": session_id},
        {"name": "@limit", "value": max_messages},
    ]

    try:
        items = list(container.query_items(
            query=query,
            parameters=params,
            partition_key=session_id,
        ))
    except Exception as e:
        logger.error(f"Cosmos query failed: {e}")
        return []

    # Reverse to chronological order
    out = []
    for item in reversed(items):
        msg = {
            "role": item["role"],
            "content": item["content"],
            "created_at": item.get("created_at"),
        }
        if item.get("products_json"):
            msg["products"] = item["products_json"]
        out.append(msg)
    return out


async def resolve_coreference(session_id: str, message: str) -> Optional[List[str]]:
    """
    Resolve 'those', 'these', 'them', 'compare those' to actual part numbers.

    Uses in-memory cache first (instant, no race condition), then Cosmos fallback.
    """
    import time

    pronouns = ["those", "these", "them", "they", "compare those", "compare them",
                "those filters", "these parts", "those parts", "compare these"]
    msg_lower = message.lower()
    if not any(p in msg_lower for p in pronouns):
        return None

    # Fix 1: Check in-memory cache first (no race condition)
    cached = _session_parts_cache.get(session_id)
    if cached:
        age = time.time() - cached["timestamp"]
        if age < 300:  # Cache valid for 5 minutes
            logger.info(f"Coreference resolved from cache: {cached['parts']} (age: {age:.1f}s)")
            return cached["parts"]
        else:
            # Expired, clean up
            del _session_parts_cache[session_id]

    # Fix 2: Cosmos DB fallback
    container = _get_container()
    if not container:
        return None

    query = (
        "SELECT c.recommended_parts FROM c "
        "WHERE c.session_id = @sid AND c.role = 'assistant' "
        "ORDER BY c.created_at DESC OFFSET 0 LIMIT 1"
    )
    params = [{"name": "@sid", "value": session_id}]

    try:
        items = list(container.query_items(
            query=query, parameters=params, partition_key=session_id
        ))
        for item in items:
            parts = item.get("recommended_parts", [])
            if parts:
                logger.info(f"Coreference resolved from Cosmos: {parts}")
                return parts
    except Exception as e:
        logger.error(f"Coreference resolution failed: {e}")

    return None


def get_cached_products(session_id: str) -> Optional[List[Any]]:
    """Get full product objects from cache for compare/follow-up."""
    import time
    cached = _session_parts_cache.get(session_id)
    if cached and (time.time() - cached["timestamp"]) < 300:
        return cached.get("product_data")
    return None


async def clear_session_history(session_id: str) -> int:
    """Delete all history for a session."""
    container = _get_container()
    if not container:
        return 0

    query = "SELECT c.id FROM c WHERE c.session_id = @sid"
    params = [{"name": "@sid", "value": session_id}]
    items = list(container.query_items(
        query=query, parameters=params, partition_key=session_id
    ))
    for item in items:
        container.delete_item(item["id"], partition_key=session_id)
    return len(items)
