from __future__ import annotations

import logging
import random
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from carenest.config import AppConfig

logger = logging.getLogger(__name__)


async def send_morning_message(bot: Bot, recipient_id: int, messages: tuple[str, ...]) -> None:
    try:
        await bot.send_message(chat_id=recipient_id, text=random.choice(messages))
    except TelegramAPIError as error:
        logger.error("Не удалось отправить утреннее сообщение: %s", error)


def build_scheduler(config: AppConfig, bot: Bot) -> AsyncIOScheduler | None:
    settings = config.scheduler
    if not settings.enabled:
        return None
    if config.recipient_id is None or not config.morning_messages:
        return None

    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        send_morning_message,
        trigger="cron",
        hour=settings.hour,
        minute=settings.minute,
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
    return scheduler
