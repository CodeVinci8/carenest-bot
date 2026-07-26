import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from carenest.config import AppConfig
from carenest.database import WishlistDatabase
from carenest.filters import AllowedUserFilter
from carenest.media import choose_shuffled_image
from carenest.texts import MOOD_BUTTON, SUPPORT_TEXT

logger = logging.getLogger(__name__)


def build_mood_router(config: AppConfig, database: WishlistDatabase) -> Router:
    router = Router(name="mood")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def mood_handler(message: Message) -> None:
        directory = (
            config.paths.memory_media
            if config.paths.memory_media.is_dir()
            else config.paths.favorite_media
        )
        photo = choose_shuffled_image(directory, database, "mood")
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
