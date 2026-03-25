"""
storybot.bot.handlers.auto
──────────────────────────
Enable / disable automatic story checks and let users choose
the polling interval via inline buttons.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..dao.settings_dao import SettingsDAO
from ..keyboards import interval_keyboard
from ..services.scheduler import remove_user_job, schedule_user_job
from .story import fetch_and_push_stories

router = Router()



@router.message(Command("auto_on"))
async def auto_on(msg: Message) -> None:
    st = await SettingsDAO.get(msg.from_user.id)
    st.auto_enabled = True
    await SettingsDAO.upsert(st)

    schedule_user_job(st.user_id, st.interval, fetch_and_push_stories)
    await msg.answer(f"✅ Auto-check enabled every <b>{st.interval} h</b>.")


@router.message(Command("auto_off"))
async def auto_off(msg: Message) -> None:
    st = await SettingsDAO.get(msg.from_user.id)
    st.auto_enabled = False
    await SettingsDAO.upsert(st)

    remove_user_job(st.user_id)
    await msg.answer("🚫 Auto-check disabled.")


# ─────────────────────────── callback: interval picker ────────────────────


@router.callback_query(F.data.startswith("interval:"))
async def change_interval(cb: CallbackQuery) -> None:
    hours = int(cb.data.split(":")[1])

    st = await SettingsDAO.get(cb.from_user.id)
    st.interval = hours
    await SettingsDAO.upsert(st)

    if st.auto_enabled:
        schedule_user_job(st.user_id, hours, fetch_and_push_stories)

    await cb.answer(f"Interval set to {hours} h")
