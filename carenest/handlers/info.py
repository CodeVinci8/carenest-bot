from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from carenest import __version__
from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter

HELP_TEXT = (
    "Команды CareNest Bot:\n"
    "/start — открыть главное меню;\n"
    "/quiz — начать или перезапустить личный квиз;\n"
    "/mood — получить знак поддержки;\n"
    "/days — узнать, сколько дней вы вместе;\n"
    "/wish — добавить желание;\n"
    "/wishlist — открыть список и удалить выбранное желание;\n"
    "/cancel — отменить ввод желания;\n"
    "/help — показать эту справку;\n"
    "/about — узнать о проекте."
)


def about_text() -> str:
    return (
        "CareNest Bot\n"
        "Небольшой персональный Telegram-бот о заботе и внимании.\n"
        f"Версия {__version__}."
    )


def build_info_router(config: AppConfig) -> Router:
    router = Router(name="info")
    allowed = AllowedUserFilter(config.allowed_ids)

    @router.message(Command("help"), allowed)
    async def help_handler(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @router.message(Command("about"), allowed)
    async def about_handler(message: Message) -> None:
        await message.answer(about_text())

    return router
