from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)

from carenest.config import AppConfig, ComplimentSettings
from carenest.database import WishlistDatabase

logger = logging.getLogger(__name__)
SPACE_RE = re.compile(r"\s+")


class ComplimentProvider(Protocol):
    async def generate(self, safe_context: tuple[str, ...]) -> str: ...


class ComplimentProviderError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


class AnthropicComplimentProvider:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
        self.client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            max_retries=0,
            timeout=12.0,
        )

    async def generate(self, safe_context: tuple[str, ...]) -> str:
        context = "\n".join(f"- {item}" for item in safe_context) or "- Без личных деталей."
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=120,
                temperature=0.8,
                system=(
                    "Напиши по-русски тёплый комплимент из одного или двух естественных "
                    "предложений. Не используй инфантильный или манипулятивный тон, "
                    "сексуальный контент, советы, выдуманные события и упоминания ИИ."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": "Разрешённый обезличенный контекст:\n" + context,
                    }
                ],
            )
        except AuthenticationError as error:
            raise ComplimentProviderError("authentication") from error
        except RateLimitError as error:
            raise ComplimentProviderError("rate_limit") from error
        except APITimeoutError as error:
            raise ComplimentProviderError("timeout") from error
        except (APIConnectionError, APIStatusError) as error:
            raise ComplimentProviderError("provider") from error
        try:
            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
        except (AttributeError, TypeError) as error:
            raise ComplimentProviderError("malformed") from error
        normalized = normalize_compliment(text)
        if not normalized:
            raise ComplimentProviderError("empty")
        return normalized


@dataclass(frozen=True)
class ComplimentRunResult:
    status: str
    source: str | None = None


def normalize_compliment(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


def is_compliment_due(
    database: WishlistDatabase,
    settings: ComplimentSettings,
    now: datetime,
) -> bool:
    local_date = now.astimezone(ZoneInfo(settings.timezone)).date()
    baseline = database.ensure_compliment_baseline(local_date)
    last_success = database.last_compliment_date()
    anchor = last_success or baseline
    return (local_date - anchor).days >= settings.interval_days


def select_local_fallback(settings: ComplimentSettings, recent: list[str]) -> str:
    normalized_recent = {normalize_compliment(item).casefold() for item in recent}
    for item in settings.local_fallbacks:
        if normalize_compliment(item).casefold() not in normalized_recent:
            return item
    return settings.local_fallbacks[0]


async def run_scheduled_compliment(
    bot: Bot,
    config: AppConfig,
    database: WishlistDatabase,
    provider: ComplimentProvider | None,
    *,
    now: datetime | None = None,
) -> ComplimentRunResult:
    settings = config.compliments
    if not settings.enabled:
        return ComplimentRunResult("disabled")
    if config.recipient_id is None:
        return ComplimentRunResult("invalid")
    current = now or datetime.now(tz=ZoneInfo("UTC"))
    if not is_compliment_due(database, settings, current):
        return ComplimentRunResult("not_due")

    recent = database.recent_compliments()
    source = "local"
    text: str
    if provider is not None:
        try:
            candidate = await provider.generate(settings.safe_context)
            if normalize_compliment(candidate).casefold() in {
                normalize_compliment(item).casefold() for item in recent
            }:
                text = select_local_fallback(settings, recent)
            else:
                text = candidate
                source = "ai"
        except ComplimentProviderError as error:
            logger.warning("Генерация комплимента не выполнена: категория %s.", error.category)
            text = select_local_fallback(settings, recent)
    else:
        text = select_local_fallback(settings, recent)

    compliment_id = database.create_compliment(text, source, current)
    try:
        await bot.send_message(chat_id=config.recipient_id, text=text)
    except (OSError, TelegramAPIError):
        database.mark_compliment_failed(compliment_id)
        logger.error("Telegram не подтвердил доставку комплимента.")
        return ComplimentRunResult("delivery_failed", source)
    local_date = current.astimezone(ZoneInfo(settings.timezone)).date()
    database.mark_compliment_delivered(compliment_id, current, local_date)
    logger.info("Комплимент доставлен; источник: %s.", source)
    return ComplimentRunResult("sent", source)
