from __future__ import annotations

import logging
import random
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from carenest.compliments import ComplimentProvider, run_scheduled_compliment
from carenest.config import AppConfig
from carenest.database import WishlistDatabase

logger = logging.getLogger(__name__)


async def send_morning_message(bot: Bot, recipient_id: int, messages: tuple[str, ...]) -> None:
    try:
        await bot.send_message(chat_id=recipient_id, text=random.choice(messages))
    except TelegramAPIError as error:
        logger.error("Не удалось отправить утреннее сообщение: %s", error)


def build_scheduler(
    config: AppConfig,
    bot: Bot,
    database: WishlistDatabase | None = None,
    compliment_provider: ComplimentProvider | None = None,
) -> AsyncIOScheduler | None:
    settings = config.scheduler
    compliment_settings = config.compliments
    if not settings.enabled and not compliment_settings.enabled:
        return None

    scheduler = AsyncIOScheduler()
    if settings.enabled and config.recipient_id is not None and config.morning_messages:
        scheduler.add_job(
            send_morning_message,
            trigger="cron",
            hour=settings.hour,
            minute=settings.minute,
            timezone=ZoneInfo(settings.timezone),
            kwargs={
                "bot": bot,
                "recipient_id": config.recipient_id,
                "messages": config.morning_messages,
            },
            id="morning-message",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )
    if compliment_settings.enabled and database is not None:
        scheduler.add_job(
            run_scheduled_compliment,
            trigger="cron",
            hour=compliment_settings.hour,
            minute=compliment_settings.minute,
            timezone=ZoneInfo(compliment_settings.timezone),
            kwargs={
                "bot": bot,
                "config": config,
                "database": database,
                "provider": compliment_provider,
            },
            id="scheduled-compliment",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=900,
        )
    return scheduler
