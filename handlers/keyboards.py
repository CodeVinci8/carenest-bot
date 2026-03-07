from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="мне грустно 🥺")],
            [KeyboardButton(text="сколько мы вместе? ⏳")],
            [KeyboardButton(text="добавить хотелку 🎁")],
            [KeyboardButton(text="мой wishlist 📝")]
        ],
        resize_keyboard=True
    )

    return keyboard