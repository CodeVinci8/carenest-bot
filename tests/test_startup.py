from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from carenest.app import prepare_database
from carenest.compliments import is_compliment_due
from carenest.config import inspect_configuration
from carenest.database import WishlistDatabase


def _enabled_config(tmp_path, monkeypatch, write_config):
    write_config(
        tmp_path,
        {
            "compliments": {
                "enabled": True,
                "interval_days": 3,
                "hour": 12,
                "minute": 0,
                "timezone": "Europe/Moscow",
                "safe_context": [],
                "local_fallbacks": ["Тёплый локальный текст."],
            }
        },
    )
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz")
    monkeypatch.setenv("ALLOWED_IDS", "100")
    monkeypatch.setenv("RECIPIENT_ID", "100")
    monkeypatch.setenv("AIPRIMETECH_API_KEY", "test-key")
    result = inspect_configuration(project_root=tmp_path)
    assert result.ok
    return result.config


def test_startup_persists_baseline_and_sends_nothing(tmp_path, monkeypatch, write_config) -> None:
    config = _enabled_config(tmp_path, monkeypatch, write_config)

    database = prepare_database(config)

    stored = database.get_state("compliments_baseline_date")
    assert stored is not None
    # Baseline is initialised at startup, not on the first cron occurrence.
    assert date.fromisoformat(stored) == datetime.now(tz=ZoneInfo("Europe/Moscow")).date()
    # No compliment is delivered at startup.
    assert database.last_compliment_date() is None
    # And it is not due on the same day the baseline was set.
    baseline_noon = datetime.combine(
        date.fromisoformat(stored),
        datetime.min.time(),
        tzinfo=ZoneInfo("Europe/Moscow"),
    ).replace(hour=12)
    assert not is_compliment_due(database, config.compliments, baseline_noon)
    assert is_compliment_due(database, config.compliments, baseline_noon + timedelta(days=3))


def test_restart_does_not_move_baseline_forward(tmp_path, monkeypatch, write_config) -> None:
    config = _enabled_config(tmp_path, monkeypatch, write_config)
    # Simulate an existing deployment whose baseline was set long ago.
    seed = WishlistDatabase(config.paths.database)
    seed.initialize()
    seed.set_state("compliments_baseline_date", "2026-01-01")

    # A restart runs the same startup path again.
    database = prepare_database(config)

    assert database.get_state("compliments_baseline_date") == "2026-01-01"


def test_disabled_compliments_write_no_baseline(tmp_path, monkeypatch, write_config) -> None:
    write_config(tmp_path)
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    assert result.config is not None
    assert not result.config.compliments.enabled

    database = prepare_database(result.config)

    assert database.get_state("compliments_baseline_date") is None
