from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мне грустно 🥺")]
        ],
        resize_keyboard=True
    )

    return keyboard