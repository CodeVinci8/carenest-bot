from dataclasses import replace
from pathlib import Path

from carenest.config import SchedulerSettings, inspect_configuration
from carenest.scheduler import build_scheduler


def test_disabled_scheduler_is_not_created(tmp_path: Path, clean_environment: None) -> None:
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    assert result.config is not None

    assert build_scheduler(result.config, object()) is None


def test_scheduler_has_duplicate_run_protection(
    tmp_path: Path,
    monkeypatch,
    clean_environment: None,
) -> None:
    monkeypatch.setenv("RECIPIENT_ID", "42")
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    assert result.config is not None
    config = replace(
        result.config,
        morning_messages=("Доброе утро!",),
        scheduler=SchedulerSettings(
            enabled=True,
            hour=8,
            minute=30,
            timezone="Europe/Moscow",
        ),
    )

    scheduler = build_scheduler(config, object())

    assert scheduler is not None
    job = scheduler.get_job("morning-message")
    assert job is not None
    assert job.coalesce is True
    assert job.max_instances == 1
    assert job.misfire_grace_time == 300
