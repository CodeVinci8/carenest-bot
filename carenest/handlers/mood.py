import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from carenest.config import AppConfig
from carenest.database import WishlistDatabase
from carenest.filters import AllowedUserFilter
from carenest.media import choose_shuffled_image
from carenest.texts import (
    FAVORITE_BUTTON,
    FAVORITE_FALLBACK_TEXT,
    FAVORITE_TEXT,
    MOOD_BUTTON,
    SUPPORT_TEXT,
)

logger = logging.getLogger(__name__)


async def send_shuffled_photo(
    message: Message,
    database: WishlistDatabase,
    directory: Path,
    category: str,
    caption: str,
    fallback_text: str,
) -> None:
    """Send one shuffled photo from ``directory`` using an isolated shuffle bag.

    Each ``category`` keeps its own persisted, non-repeating shuffle state, so the
    memory pool and the favourite pool never draw from or exhaust each other. Any
    missing directory, empty pool or delivery error falls back to plain text.
    """
    if not directory.is_dir():
        await message.answer(fallback_text)
        return
    photo = choose_shuffled_image(directory, database, category)
    if photo is None:
        await message.answer(fallback_text)
        return
    try:
        await message.answer_photo(photo=FSInputFile(photo), caption=caption)
    except (OSError, TelegramAPIError) as error:
        logger.warning("Не удалось отправить фотографию (%s): %s", category, error)
        await message.answer(fallback_text)


def build_mood_router(config: AppConfig, database: WishlistDatabase) -> Router:
    router = Router(name="mood")
    allowed = AllowedUserFilter(config.allowed_ids)

    async def mood_handler(message: Message) -> None:
        # /mood is dedicated to the random-memory pool only.
        await send_shuffled_photo(
            message,
            database,
            config.paths.memory_media,
            "mood",
            SUPPORT_TEXT,
            SUPPORT_TEXT,
        )

    async def favorite_handler(message: Message) -> None:
        # /favorite draws from the independent favourite-photo pool.
        await send_shuffled_photo(
            message,
            database,
            config.paths.favorite_media,
            "favorites",
            FAVORITE_TEXT,
            FAVORITE_FALLBACK_TEXT,
        )

    router.message.register(mood_handler, Command("mood"), allowed)
    router.message.register(mood_handler, F.text == MOOD_BUTTON, allowed)
    router.message.register(favorite_handler, Command("favorite"), allowed)
    router.message.register(favorite_handler, F.text == FAVORITE_BUTTON, allowed)
    return router
