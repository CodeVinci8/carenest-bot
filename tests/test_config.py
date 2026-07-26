from pathlib import Path

import pytest

from carenest.config import inspect_configuration


def test_example_check_ignores_private_config_path(
    tmp_path, monkeypatch, clean_environment
) -> None:
    example = tmp_path / "config" / "personalization.example.json"
    example.parent.mkdir(parents=True)
    example.write_text('{"quiz": {"questions": []}}', encoding="utf-8")
    monkeypatch.setenv("CARENEST_CONFIG", "private/missing.json")

    result = inspect_configuration(
        project_root=tmp_path,
        require_secrets=False,
        example=True,
    )

    assert result.config.paths.config_file == example.resolve()


def set_required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz_ABCDE")
    monkeypatch.setenv("ALLOWED_IDS", "101, 202")


def test_missing_required_environment_is_reported(
    tmp_path: Path,
    clean_environment: None,
) -> None:
    result = inspect_configuration(project_root=tmp_path)

    assert not result.ok
    assert "Не задан TELEGRAM_TOKEN." in result.errors
    assert any("ALLOWED_IDS" in error for error in result.errors)


def test_valid_configuration_is_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_environment: None,
    write_config,
) -> None:
    write_config(tmp_path)
    set_required_environment(monkeypatch)

    result = inspect_configuration(project_root=tmp_path)

    assert result.ok
    assert result.config is not None
    assert result.config.allowed_ids == frozenset({101, 202})
    assert len(result.config.questions) == 1


def test_paths_do_not_depend_on_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_environment: None,
    write_config,
) -> None:
    write_config(tmp_path)
    set_required_environment(monkeypatch)
    foreign_directory = tmp_path / "outside" / "nested"
    foreign_directory.mkdir(parents=True)
    monkeypatch.chdir(foreign_directory)

    result = inspect_configuration(project_root=tmp_path)

    assert result.config is not None
    assert result.config.paths.database == (tmp_path / "data" / "wishlist.db").resolve()
    assert result.config.paths.quiz_media == (tmp_path / "media" / "quiz").resolve()


def test_invalid_quiz_answer_index_is_reported(
    tmp_path: Path,
    clean_environment: None,
    write_config,
) -> None:
    write_config(
        tmp_path,
        {
            "quiz": {
                "questions": [
                    {
                        "question": "Вопрос",
                        "options": ["Один", "Два"],
                        "correct": 4,
                    }
                ]
            }
        },
    )

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert not result.ok
    assert any("correct" in error for error in result.errors)


def test_legacy_quiz_file_is_loaded_without_import(
    tmp_path: Path,
    clean_environment: None,
) -> None:
    (tmp_path / "quiz_data.py").write_text(
        'QUESTIONS = [{"question": "Вопрос?", "photo": None, '
        '"options": ["Да", "Нет"], "correct": 0}]\n',
        encoding="utf-8",
    )

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert result.ok
    assert result.config is not None
    assert result.config.questions[0].question == "Вопрос?"
    assert any("quiz_data.py" in warning for warning in result.warnings)


def test_her_id_is_a_deprecated_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clean_environment: None,
) -> None:
    monkeypatch.setenv("HER_ID", "303")

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert result.config is not None
    assert result.config.recipient_id == 303
    assert result.config.recipient_id_source == "HER_ID"
    assert any("устаревший HER_ID" in warning for warning in result.warnings)


def test_invalid_scheduler_timezone_stops_validation(
    tmp_path: Path,
    clean_environment: None,
    write_config,
) -> None:
    write_config(
        tmp_path,
        {
            "scheduler": {
                "enabled": False,
                "hour": 9,
                "minute": 0,
                "timezone": "Mars/Olympus",
            }
        },
    )

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert not result.ok
    assert any("часовой пояс" in error for error in result.errors)


def test_invalid_final_message_template_is_reported(
    tmp_path: Path,
    clean_environment: None,
    write_config,
) -> None:
    write_config(tmp_path, {"final_quiz_message": "Неизвестное поле: {unknown}"})

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert not result.ok
    assert any("final_quiz_message" in error for error in result.errors)


def test_database_path_cannot_be_a_directory(
    tmp_path: Path,
    clean_environment: None,
    write_config,
) -> None:
    write_config(tmp_path)
    database_path = tmp_path / "data" / "wishlist.db"
    database_path.mkdir(parents=True)

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert not result.ok
    assert any("Путь к базе данных" in error for error in result.errors)


def test_enabled_scheduler_requires_recipient_and_messages(
    tmp_path: Path,
    clean_environment: None,
    write_config,
) -> None:
    write_config(
        tmp_path,
        {
            "scheduler": {
                "enabled": True,
                "hour": 9,
                "minute": 0,
                "timezone": "Europe/Moscow",
            },
            "morning_messages": [],
        },
    )

    result = inspect_configuration(project_root=tmp_path, require_secrets=False)

    assert not result.ok
    assert any("RECIPIENT_ID" in error for error in result.errors)
    assert any("morning_messages" in error for error in result.errors)
