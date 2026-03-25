"""
storybot.bot.handlers.story
───────────────────────────
Fetch and deliver Instagram stories on demand (/story or plain username)
and from APScheduler (auto-check).

Public
------
fetch_and_push_stories(user_id: int)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from aiogram import Router, F, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message

from ..config import settings
from ..dao.settings_dao import SettingsDAO
from ..keyboards import interval_keyboard
from ..services.api_client import APIClient
from ..services.auth_token import AuthTokenManager
from ..services.browser import BrowserManager
from ..services.url_decoder import URLDecoder

log = logging.getLogger(__name__)
router = Router()

_api_client = APIClient()
_browser_mgr = BrowserManager()

# Lazily initialised shared Bot for background jobs (auto-check).
_shared_bot: Bot | None = None


def _get_bot() -> Bot:
    global _shared_bot
    if _shared_bot is None:
        _shared_bot = Bot(
            token=settings.tg_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
    return _shared_bot


async def fetch_and_push_stories(user_id: int) -> None:
    """Background task executed by APScheduler."""
    profile = await SettingsDAO.get(user_id)
    if not profile.target_username:
        log.info("auto-job skipped: user %s has no target_username", user_id)
        return

    bot = _get_bot()
    status = await bot.send_message(
        user_id,
        f"🔄 Auto-check @{profile.target_username} …",
    )

    await _process_username(bot, user_id, status, profile.target_username)


@router.message(Command("story"))
async def cmd_story(msg: Message) -> None:
    await msg.answer("✍️ Enter an Instagram username (without @):")


@router.message(~F.text.startswith("/"))
async def handle_username(msg: Message) -> None:
    username = _validate_username(msg.text)
    if not username:
        await msg.answer("⚠️ Please provide a valid username.")
        return

    profile = await SettingsDAO.get(msg.from_user.id)
    profile.target_username = username
    await SettingsDAO.upsert(profile)

    status = await msg.answer(f"🔎 Looking up @{username} …")
    success = await _process_username(msg.bot, msg.chat.id, status, username)

    if success:
        await msg.answer(
            "⚙️ Choose an auto-check interval:",
            reply_markup=interval_keyboard(),
        )


async def _process_username(
    bot: Bot,
    chat_id: int,
    status: Message,
    username: str,
) -> bool:
    """Shared routine; returns *True* if at least one story was sent."""
    try:
        auth_token = AuthTokenManager.build_auth_token(username)

        await status.edit_text("🌐 Launching headless browser …")
        await _browser_mgr.trigger_browser_async(username)

        await status.edit_text("⌛ Querying anonstories API …")
        data = await _api_client.wait_for_stories(auth_token)
        if not data:
            await status.edit_text(
                "❌ Nothing found (private or non-existent account)."
            )
            return False

        await _send_profile_info(bot, chat_id, data["user_info"])

        stories = data["stories"]
        if not stories:
            await status.edit_text("ℹ️ The account currently has no active stories.")
            return False

        await status.edit_text(f"📲 Found {len(stories)} stories — sending …")
        for idx, story in enumerate(stories, 1):
            await _send_single_story(bot, chat_id, story, idx, len(stories))
            if idx < len(stories):
                await asyncio.sleep(0.4)

        await SettingsDAO.add_search(
            user_id=chat_id,
            username=username,
            sent=len(stories),
        )

        await status.delete()
        return True

    except Exception as exc:
        log.exception("Failed to fetch %s: %s", username, exc)
        await status.edit_text("💥 An error occurred while fetching stories.")
        return False


async def _send_profile_info(
    bot: Bot, chat_id: int, info: Dict[str, Any]
) -> None:
    avatar = URLDecoder.decode_embed_url(info.get("profile_pic_url", ""))

    caption = (
        "👤 <b>Instagram profile</b>\n"
        f"• @{info['username']}\n"
        f"• Name: {info.get('full_name') or '—'}\n"
        f"• Posts: {info['posts']:,}\n"
        f"• Followers: {info['followers']:,}\n"
        f"• Following: {info['following']:,}"
    )

    try:
        if avatar.startswith(("http://", "https://")):
            await bot.send_photo(chat_id, avatar, caption=caption)
        else:
            await bot.send_message(chat_id, caption)
    except Exception as exc:
        log.warning("send_profile_info: %s", exc)
        await bot.send_message(chat_id, caption)


async def _send_single_story(
    bot: Bot,
    chat_id: int,
    story: Dict[str, Any],
    idx: int,
    total: int,
) -> None:
    src = URLDecoder.decode_embed_url(story["source"])
    caption = f"📖 Story {idx}/{total}"

    try:
        if story["media_type"] == "image":
            await bot.send_photo(chat_id, src, caption=caption)
        else:
            await bot.send_video(chat_id, src, caption=caption)
    except Exception as exc:
        log.warning("Story %s/%s failed: %s", idx, total, exc)


def _validate_username(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    name = raw.strip().lstrip("@").lower()
    ok = 1 <= len(name) <= 30 and name.replace("_", "").replace(".", "").isalnum()
    return name if ok else None
