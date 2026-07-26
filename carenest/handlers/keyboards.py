from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from carenest.texts import (
    ABOUT_BUTTON,
    ADD_WISH_BUTTON,
    HELP_BUTTON,
    MOOD_BUTTON,
    QUIZ_BUTTON,
    RELATIONSHIP_BUTTON,
    WISHLIST_BUTTON,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=QUIZ_BUTTON), KeyboardButton(text=MOOD_BUTTON)],
            [KeyboardButton(text=RELATIONSHIP_BUTTON), KeyboardButton(text=WISHLIST_BUTTON)],
            [KeyboardButton(text=ADD_WISH_BUTTON)],
            [KeyboardButton(text=HELP_BUTTON), KeyboardButton(text=ABOUT_BUTTON)],
        ],
        resize_keyboard=True,
    )
