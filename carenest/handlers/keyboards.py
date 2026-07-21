from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from carenest.texts import ADD_WISH_BUTTON, MOOD_BUTTON, RELATIONSHIP_BUTTON, WISHLIST_BUTTON


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MOOD_BUTTON)],
            [KeyboardButton(text=RELATIONSHIP_BUTTON)],
            [KeyboardButton(text=ADD_WISH_BUTTON)],
            [KeyboardButton(text=WISHLIST_BUTTON)],
        ],
        resize_keyboard=True,
    )
