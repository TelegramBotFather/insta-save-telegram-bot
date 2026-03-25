"""
storybot.bot.services.browser
─────────────────────────────
Launches a headless Chrome session so that anonstories prepares JSON for us.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import undetected_chromedriver as uc

_BROWSERS_SEMAPHORE = asyncio.Semaphore(3)
BROWSER_TIMEOUT = 30  # seconds

log = logging.getLogger(__name__)


class BrowserManager:
    """Spawn short-lived headless Chrome sessions."""

    _options: uc.ChromeOptions | None = None

    @classmethod
    def _get_options(cls) -> uc.ChromeOptions:
        if cls._options is None:
            opts = uc.ChromeOptions()
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument(
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            )
            opts.binary_location = os.getenv(
                "CHROME_BINARY", "/usr/bin/google-chrome"
            )
            cls._options = opts
        return cls._options

    async def trigger_browser_async(self, username: str) -> None:
        """Run _open_page in a thread-executor, limited by a semaphore."""
        loop = asyncio.get_running_loop()
        async with _BROWSERS_SEMAPHORE:
            await loop.run_in_executor(None, self._open_page, username)

    def _open_page(self, username: str) -> None:
        url = f"https://anonstories.com/view/{username}"
        log.debug("Headless Chrome → %s", url)

        driver = None
        try:
            driver = uc.Chrome(
                options=self._get_options(), driver_executable_path=None
            )
            driver.set_page_load_timeout(BROWSER_TIMEOUT)
            driver.get(url)
            driver.find_element("tag name", "body")
            log.debug("Page loaded for %s", username)
        except Exception as exc:
            log.warning("Browser error for %s: %s", username, exc)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
