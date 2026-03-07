from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мне грустно 🥺")],
            [KeyboardButton(text="Сколько мы вместе? ⏳")]
        ],
        resize_keyboard=True
    )

    return keyboard