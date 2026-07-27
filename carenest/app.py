from __future__ import annotations

import logging
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from carenest.compliments import (
    OpenAICompatibleComplimentProvider,
    initialize_compliment_baseline,
)
from carenest.config import AppConfig
from carenest.database import WishlistDatabase
from carenest.handlers import (
    build_info_router,
    build_mood_router,
    build_quiz_router,
    build_start_router,
    build_wishlist_router,
)
from carenest.scheduler import build_scheduler
from carenest.version import __version__

logger = logging.getLogger(__name__)

BOT_COMMANDS = (
    BotCommand(command="start", description="открыть меню"),
    BotCommand(command="quiz", description="сыграем в квиз"),
    BotCommand(command="mood", description="случайный момент"),
    BotCommand(command="favorite", description="любимое фото"),
    BotCommand(command="wish", description="загадать желание"),
    BotCommand(command="wishlist", description="мой вишлист"),
    BotCommand(command="cancel", description="отменить"),
    BotCommand(command="help", description="что я умею"),
    BotCommand(command="about", description="о боте"),
)


def build_dispatcher(config: AppConfig, database: WishlistDatabase) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(build_start_router(config))
    dispatcher.include_router(build_info_router(config))
    dispatcher.include_router(build_quiz_router(config))
    dispatcher.include_router(build_mood_router(config, database))
    dispatcher.include_router(build_wishlist_router(config, database))
    return dispatcher


async def set_main_menu(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)
    logger.info("Команды Telegram зарегистрированы.")


def prepare_database(config: AppConfig) -> WishlistDatabase:
    """Create and initialize the runtime database (the real startup path).

    When compliments are enabled the three-day interval baseline is persisted
    here, at startup, rather than on the first cron occurrence. Because the
    baseline is written only if absent, restarts never move it forward and no
    startup or catch-up compliment is triggered.
    """
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    if config.compliments.enabled:
        initialize_compliment_baseline(database, config.compliments)
    return database


async def run_bot(config: AppConfig) -> None:
    logger.info("Запуск %s %s.", config.product_name, __version__)
    logger.info("Подготовка локальной базы данных.")
    try:
        database = prepare_database(config)
    except (OSError, sqlite3.Error) as error:
        raise RuntimeError(f"Не удалось подготовить локальную базу данных: {error}") from error
    logger.info("Локальная база данных готова.")

    if config.token is None:
        raise RuntimeError("После проверки конфигурации отсутствует TELEGRAM_TOKEN.")

    bot = Bot(token=config.token)
    dispatcher = build_dispatcher(config, database)
    compliment_provider = None
    if config.compliments.enabled and config.compliments.api_key:
        compliment_provider = OpenAICompatibleComplimentProvider(
            config.compliments.api_key,
            config.compliments.base_url,
            config.compliments.model,
        )
    scheduler = build_scheduler(config, bot, database, compliment_provider)
    try:
        await set_main_menu(bot)
        if scheduler is not None:
            scheduler.start()
            logger.info("Планировщик CareNest запущен.")
        else:
            logger.info("Планировщик CareNest выключен.")
        logger.info("%s запущен.", config.product_name)
        await dispatcher.start_polling(bot, close_bot_session=False)
    except TelegramAPIError as error:
        logger.error("Ошибка Telegram при работе бота: %s", error)
        raise
    finally:
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Планировщик остановлен.")
        await bot.session.close()
        logger.info("Сессия Telegram закрыта. %s остановлен.", config.product_name)
