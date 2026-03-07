import datetime

from aiogram import Router, F
from aiogram.types import Message

from filters.allowed_users import AllowedUserFilter

router = Router()


def day_word(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    if 2 <= days % 10 <= 4 and not 12 <= days % 100 <= 14:
        return "дня"
    return "дней"


@router.message(F.text, F.text.lower() == "сколько мы вместе? ⏳", AllowedUserFilter())
async def relationship_days_handler(message: Message):
    start_date = datetime.date(2024, 9, 21)
    today = datetime.date.today()

    days_together = (today - start_date).days
    word = day_word(days_together)

    await message.answer(
        f"⏳ мы вместе уже\n\n{days_together} {word} ❤️"
    )