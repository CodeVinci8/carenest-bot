import datetime

from aiogram import Router, F
from aiogram.types import Message

from filters.allowed_users import AllowedUserFilter

router = Router()


@router.message(F.text == "Сколько мы вместе? ⏳", AllowedUserFilter())
async def relationship_days_handler(message: Message):

    start_date = datetime.date(2024, 9, 21)
    today = datetime.date.today()

    days_together = (today - start_date).days

    await message.answer(
        await message.answer(
    f"⏳ Мы вместе уже\n\n{days_together} дня ❤️"
        )
    )