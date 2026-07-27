from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from carenest import __version__
from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.texts import ABOUT_BUTTON, HELP_BUTTON


def help_text(product_name: str = "CareNest Bot") -> str:
    return (
        f"вот что умеет {product_name}:\n"
        "/start — вернуться в меню;\n"
        "/quiz — сыграем в квиз;\n"
        "/mood — случайный тёплый момент;\n"
        "/favorite — любимое фото;\n"
        "/wish — загадать желание;\n"
        "/wishlist — открыть вишлист и убрать лишнее;\n"
        "/cancel — отменить желание;\n"
        "/help — показать это ещё раз;\n"
        "/about — пару слов о боте."
    )


HELP_TEXT = help_text()


def about_text(product_name: str = "CareNest Bot") -> str:
    return f"{product_name}\nмаленький бот про заботу и тёплые моменты 💛\nверсия {__version__}."


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
