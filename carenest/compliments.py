from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from carenest.config import AppConfig, ComplimentSettings
from carenest.database import WishlistDatabase

logger = logging.getLogger(__name__)
SPACE_RE = re.compile(r"\s+")

COMPLIMENT_SYSTEM_PROMPT = (
    "Напиши по-русски тёплый комплимент из одного или двух естественных "
    "предложений. Не используй инфантильный или манипулятивный тон, "
    "сексуальный контент, советы, выдуманные события и упоминания ИИ."
)


class ComplimentProvider(Protocol):
    async def generate(self, safe_context: tuple[str, ...]) -> str: ...


class ComplimentProviderError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def _normalize_openai_base_url(base_url: str) -> str:
    """Return an OpenAI-compatible API root (…/v1) for the gateway."""
    root = base_url.rstrip("/")
    if root.endswith("/v1") or "/v1/" in root:
        return root
    return f"{root}/v1"


class OpenAICompatibleComplimentProvider:
    """Compliment provider for the AI Prime Tech OpenAI-compatible gateway.

    The stored key belongs to the Codex model group (gpt-5.6-luna / -sol / -terra)
    and speaks the OpenAI Chat Completions protocol. It is not an Anthropic/Claude
    key, so no Claude model is ever requested here.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=_normalize_openai_base_url(base_url),
            max_retries=0,
            timeout=12.0,
        )

    async def generate(self, safe_context: tuple[str, ...]) -> str:
        context = "\n".join(f"- {item}" for item in safe_context) or "- Без личных деталей."
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=256,
                messages=[
                    {"role": "system", "content": COMPLIMENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": "Разрешённый обезличенный контекст:\n" + context,
                    },
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
        except OpenAIError as error:
            raise ComplimentProviderError("provider") from error
        try:
            choices = response.choices
            message = choices[0].message
            text = message.content or ""
        except (AttributeError, IndexError, KeyError, TypeError) as error:
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


def initialize_compliment_baseline(
    database: WishlistDatabase,
    settings: ComplimentSettings,
    now: datetime | None = None,
) -> date:
    """Persist the interval baseline at application startup.

    The baseline is written once (INSERT-if-absent), so a restart never moves an
    existing baseline forward and no catch-up compliment is produced.
    """
    current = now or datetime.now(tz=ZoneInfo("UTC"))
    local_date = current.astimezone(ZoneInfo(settings.timezone)).date()
    return database.ensure_compliment_baseline(local_date)


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
