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

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.environ.get("COSMOS_KEY", "")
COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE", "enpro-fm")
COSMOS_CONTAINER = "conversations"

_container = None


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
        "SELECT c.role, c.content, c.created_at, c.products_json "
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
