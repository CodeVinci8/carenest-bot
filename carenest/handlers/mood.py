import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from carenest.config import AppConfig
from carenest.filters import AllowedUserFilter
from carenest.media import choose_random_image
from carenest.texts import MOOD_BUTTON, SUPPORT_TEXT

logger = logging.getLogger(__name__)


def build_mood_router(config: AppConfig) -> Router:
    router = Router(name="mood")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def mood_handler(message: Message) -> None:
        photo = choose_random_image(config.paths.support_media)
        if photo is None:
            await message.answer(SUPPORT_TEXT)
            return
        try:
            await message.answer_photo(photo=FSInputFile(photo), caption=SUPPORT_TEXT)
        except (OSError, TelegramAPIError) as error:
            logger.warning("Не удалось отправить фотографию поддержки: %s", error)
            await message.answer(SUPPORT_TEXT)

    router.message.register(mood_handler, Command("mood"), allowed)
    router.message.register(mood_handler, F.text == MOOD_BUTTON, allowed)
    return router
