from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from carenest.compliments import (
    ComplimentProviderError,
    is_compliment_due,
    run_scheduled_compliment,
)
from carenest.config import inspect_configuration
from carenest.database import WishlistDatabase


class FakeProvider:
    def __init__(self, result: str = "Тёплый тестовый комплимент.", error: str | None = None):
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    async def generate(self, safe_context: tuple[str, ...], profile: tuple[str, ...] = ()) -> str:
        self.calls.append((safe_context, profile))
        if self.error:
            raise ComplimentProviderError(self.error)
        return self.result


class FakeBot:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        if self.fail:
            raise OSError("network")
        self.messages.append((chat_id, text))


def enabled_config(tmp_path, monkeypatch, write_config):
    write_config(
        tmp_path,
        {
            "compliments": {
                "enabled": True,
                "interval_days": 3,
                "hour": 18,
                "minute": 30,
                "timezone": "Europe/Moscow",
                "safe_context": ["Любит спокойный юмор."],
                "compliment_profile": ["Ценит внимание к мелочам."],
                "local_fallbacks": [
                    "Твоя внимательность делает мир теплее.",
                    "С тобой в обычном дне больше света.",
                ],
            }
        },
    )
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz")
    monkeypatch.setenv("ALLOWED_IDS", "100,200")
    monkeypatch.setenv("RECIPIENT_ID", "100")
    monkeypatch.setenv("AIPRIMETECH_API_KEY", "test-key")
    result = inspect_configuration(project_root=tmp_path)
    assert result.ok
    return result.config


def test_first_start_is_not_due_and_three_days_are_required(
    tmp_path, monkeypatch, write_config
) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 1, 10, 18, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    assert not is_compliment_due(database, config.compliments, start)
    assert not is_compliment_due(database, config.compliments, start + timedelta(days=2))
    assert is_compliment_due(database, config.compliments, start + timedelta(days=3))


@pytest.mark.asyncio
async def test_disabled_compliments_do_not_call_provider(
    tmp_path, monkeypatch, write_config
) -> None:
    write_config(tmp_path)
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    database = WishlistDatabase(result.config.paths.database)
    database.initialize()
    provider = FakeProvider()

    run = await run_scheduled_compliment(FakeBot(), result.config, database, provider)

    assert run.status == "disabled"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_success_is_restart_safe_and_provider_called_once(
    tmp_path, monkeypatch, write_config
) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 2, 1, 18, 30, tzinfo=ZoneInfo("Europe/Moscow"))
    assert not is_compliment_due(database, config.compliments, start)
    due = start + timedelta(days=3)
    provider = FakeProvider()
    bot = FakeBot()

    first = await run_scheduled_compliment(bot, config, database, provider, now=due)
    reopened = WishlistDatabase(config.paths.database)
    second = await run_scheduled_compliment(bot, config, reopened, provider, now=due)

    assert first.status == "sent"
    assert second.status == "not_due"
    assert len(provider.calls) == 1
    assert len(bot.messages) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category",
    ["timeout", "authentication", "rate_limit", "malformed", "empty"],
)
async def test_provider_failures_use_local_fallback(
    category, tmp_path, monkeypatch, write_config
) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 3, 1, tzinfo=ZoneInfo("Europe/Moscow"))
    assert not is_compliment_due(database, config.compliments, start)
    bot = FakeBot()

    result = await run_scheduled_compliment(
        bot,
        config,
        database,
        FakeProvider(error=category),
        now=start + timedelta(days=3),
    )

    assert result.status == "sent"
    assert result.source == "local"
    assert bot.messages[0][1] in config.compliments.local_fallbacks


@pytest.mark.asyncio
async def test_provider_error_log_does_not_contain_secret(
    tmp_path, monkeypatch, write_config, caplog
) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 3, 10, tzinfo=ZoneInfo("Europe/Moscow"))
    assert not is_compliment_due(database, config.compliments, start)

    await run_scheduled_compliment(
        FakeBot(),
        config,
        database,
        FakeProvider(error="authentication"),
        now=start + timedelta(days=3),
    )

    assert "test-key" not in caplog.text
    assert "authentication" in caplog.text


@pytest.mark.asyncio
async def test_duplicate_is_replaced_and_only_allowed_context_reaches_provider(
    tmp_path, monkeypatch, write_config
) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 4, 1, tzinfo=ZoneInfo("Europe/Moscow"))
    database.ensure_compliment_baseline(start.date())
    old_id = database.create_compliment("Тёплый тестовый комплимент.", "ai", start)
    database.mark_compliment_delivered(old_id, start, start.date())
    provider = FakeProvider()
    bot = FakeBot()

    result = await run_scheduled_compliment(
        bot, config, database, provider, now=start + timedelta(days=3)
    )

    assert result.source == "local"
    assert bot.messages[0][1] != provider.result
    # Only the approved safe_context and compliment_profile reach the provider.
    assert provider.calls == [(("Любит спокойный юмор.",), ("Ценит внимание к мелочам.",))]


@pytest.mark.asyncio
async def test_telegram_failure_does_not_mark_success(tmp_path, monkeypatch, write_config) -> None:
    config = enabled_config(tmp_path, monkeypatch, write_config)
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    start = datetime(2026, 5, 1, tzinfo=ZoneInfo("Europe/Moscow"))
    assert not is_compliment_due(database, config.compliments, start)

    result = await run_scheduled_compliment(
        FakeBot(fail=True),
        config,
        database,
        FakeProvider(),
        now=start + timedelta(days=3),
    )

    assert result.status == "delivery_failed"
    assert database.last_compliment_date() is None


def test_recipient_must_belong_to_allowlist(tmp_path, monkeypatch, write_config) -> None:
    write_config(tmp_path)
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz")
    monkeypatch.setenv("ALLOWED_IDS", "100")
    monkeypatch.setenv("RECIPIENT_ID", "200")

    result = inspect_configuration(project_root=tmp_path)

    assert not result.ok
    assert any("RECIPIENT_ID должен входить" in error for error in result.errors)
