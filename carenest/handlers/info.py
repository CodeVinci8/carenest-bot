from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from carenest import __version__
from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.texts import ABOUT_BUTTON, HELP_BUTTON


def help_text(product_name: str = "CareNest Bot") -> str:
    return (
        f"Команды {product_name}:\n"
        "/start — открыть главное меню;\n"
        "/quiz — начать или перезапустить личный квиз;\n"
        "/mood — открыть случайное воспоминание;\n"
        "/favorite — показать любимое фото;\n"
        "/days — узнать, сколько дней вы вместе;\n"
        "/wish — добавить желание;\n"
        "/wishlist — открыть список и удалить выбранное желание;\n"
        "/cancel — отменить ввод желания;\n"
        "/help — показать эту справку;\n"
        "/about — узнать о проекте."
    )


HELP_TEXT = help_text()


def about_text(product_name: str = "CareNest Bot") -> str:
    return (
        f"{product_name}\n"
        "Небольшой персональный Telegram-бот о заботе и внимании.\n"
        f"Версия {__version__}."
    )


def build_info_router(config: AppConfig) -> Router:
    router = Router(name="info")
    allowed = AllowedUserFilter(config.allowed_ids)

    @router.message(Command("help"), allowed)
    async def help_handler(message: Message) -> None:
        await message.answer(help_text(config.product_name))

    @router.message(Command("about"), allowed)
    async def about_handler(message: Message) -> None:
        await message.answer(about_text(config.product_name))

    router.message.register(help_handler, F.text == HELP_BUTTON, allowed)
    router.message.register(about_handler, F.text == ABOUT_BUTTON, allowed)

    return router
