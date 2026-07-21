from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.texts import RELATIONSHIP_BUTTON


def day_word(days: int) -> str:
    absolute = abs(days)
    if absolute % 10 == 1 and absolute % 100 != 11:
        return "день"
    if 2 <= absolute % 10 <= 4 and not 12 <= absolute % 100 <= 14:
        return "дня"
    return "дней"


def relationship_days(start_date: date, today: date | None = None) -> int:
    return ((today or date.today()) - start_date).days


def build_relationship_router(config: AppConfig) -> Router:
    router = Router(name="relationship")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def relationship_handler(message: Message) -> None:
        if config.relationship_start_date is None:
            await message.answer("Дата начала отношений пока не настроена.")
            return
        days = relationship_days(config.relationship_start_date)
        if days < 0:
            await message.answer("Дата начала отношений указана в будущем. Проверьте конфигурацию.")
            return
        await message.answer(f"Мы вместе уже {days} {day_word(days)}. ❤️")

    router.message.register(relationship_handler, Command("days"), allowed)
    router.message.register(relationship_handler, F.text == RELATIONSHIP_BUTTON, allowed)
    return router
