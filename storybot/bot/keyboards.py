from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def interval_keyboard() -> InlineKeyboardMarkup:
    """Return an inline-keyboard with common auto-check intervals."""
    rows = [
        [
            InlineKeyboardButton(text="1 h", callback_data="interval:1"),
            InlineKeyboardButton(text="3 h", callback_data="interval:3"),
            InlineKeyboardButton(text="6 h", callback_data="interval:6"),
        ],
        [
            InlineKeyboardButton(text="8 h", callback_data="interval:8"),
            InlineKeyboardButton(text="12 h", callback_data="interval:12"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
