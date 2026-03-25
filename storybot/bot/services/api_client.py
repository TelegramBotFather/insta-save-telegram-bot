"""
storybot.bot.services.api_client
────────────────────────────────
Async wrapper around anonstories.com API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)

API_ENDPOINT = "https://anonstories.com/api/v1/story"
API_TIMEOUT = 30          # seconds
POLL_DELAY = 3            # base seconds between polls
MAX_RETRIES = 10          # max polling attempts


class APIClient:
    """Lightweight async client for anonstories.com."""

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            " AppleWebKit/537.36 (KHTML, like Gecko)"
        ),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    def __init__(self, timeout: int = API_TIMEOUT) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self._HEADERS,
                timeout=self._timeout,
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_story_data(self, auth_token: str) -> Dict[str, Any]:
        """Single POST request, returns raw JSON or empty dict on failure."""
        try:
            sess = await self._get_session()
            async with sess.post(API_ENDPOINT, data={"auth": auth_token}) as r:
                if r.status != 200:
                    log.warning("anonstories HTTP %s", r.status)
                    return {}
                return await r.json()
        except asyncio.TimeoutError:
            log.warning("anonstories request timed-out")
            return {}
        except Exception as exc:
            log.exception("anonstories error: %s", exc)
            return {}

    async def wait_for_stories(
        self, auth_token: str, max_retries: int = MAX_RETRIES
    ) -> Optional[Dict[str, Any]]:
        """
        Poll anonstories with exponential back-off until stories arrive
        or *max_retries* is reached.
        """
        for attempt in range(max_retries):
            delay = min(POLL_DELAY * (2 ** (attempt // 3)), 30)
            if attempt:
                await asyncio.sleep(delay)

            data = await self.fetch_story_data(auth_token)
            if data.get("user_info") and data.get("stories") is not None:
                return data

        log.warning("anonstories: no data after %s retries", max_retries)
        return None
