"""
Append-only statistics DAO.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict

from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, Field

from .settings_dao import _get_client

log = logging.getLogger(__name__)

_stats_index_created = False


def _get_collection() -> AsyncIOMotorCollection:
    """Lazy access to the stats collection."""
    return _get_client().get_default_database().stats


async def _ensure_indexes() -> None:
    global _stats_index_created
    if not _stats_index_created:
        coll = _get_collection()
        await coll.create_index(
            [("user_id", 1), ("date", 1), ("target_username", 1)]
        )
        await coll.create_index("ts")
        _stats_index_created = True
        log.debug("stats indexes created")


class StatsRecord(BaseModel):
    user_id: int
    target_username: str
    date: str = Field(default_factory=lambda: date.today().isoformat())
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fetched: int = 1
    sent: int = 0


class StatsDAO:
    """Append-only event logger."""

    @classmethod
    async def add(cls, user_id: int, username: str, sent: int) -> None:
        await _ensure_indexes()
        rec: Dict[str, Any] = StatsRecord(
            user_id=user_id,
            target_username=username.lower(),
            sent=sent,
        ).model_dump()
        await _get_collection().insert_one(rec)
