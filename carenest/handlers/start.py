from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.handlers.keyboards import get_main_keyboard

START_TEXT = (
    "Добро пожаловать в CareNest Bot. Здесь можно сохранить желание, вспомнить, "
    "сколько дней вы вместе, пройти личный квиз или получить небольшой знак поддержки. "
    "Краткая справка доступна по команде /help."
)


def build_start_router(config: AppConfig) -> Router:
    router = Router(name="start")

    @router.message(CommandStart(), AllowedUserFilter(config.allowed_ids))
    async def start_handler(message: Message) -> None:
        await message.answer(START_TEXT, reply_markup=get_main_keyboard())

    return router
