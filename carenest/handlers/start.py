from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.handlers.keyboards import get_main_keyboard


def start_text(product_name: str) -> str:
    return (
        f"Добро пожаловать в {product_name}. Здесь можно сохранить желание, вспомнить, "
        "сколько дней вы вместе, пройти личный квиз или открыть случайное воспоминание. "
        "Краткая справка доступна по команде /help."
    )


def build_start_router(config: AppConfig) -> Router:
    router = Router(name="start")

    @router.message(CommandStart(), AllowedUserFilter(config.allowed_ids))
    async def start_handler(message: Message) -> None:
        await message.answer(start_text(config.product_name), reply_markup=get_main_keyboard())

    return router
