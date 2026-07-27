import json
from pathlib import Path

import pytest


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TELEGRAM_TOKEN",
        "ALLOWED_IDS",
        "RECIPIENT_ID",
        "HER_ID",
        "CARENEST_CONFIG",
        "CARENEST_DATA_DIR",
        "CARENEST_PRODUCT_NAME",
        "AIPRIMETECH_API_KEY",
        "AIPRIMETECH_BASE_URL",
        "AIPRIMETECH_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def write_config():
    def writer(root: Path, overrides: dict | None = None) -> Path:
        data = {
            "recipient_name": "близкий человек",
            "final_quiz_message": "Квиз завершён: {code_word}",
            "code_word": "пример",
            "morning_messages": ["Доброе утро!"],
            "scheduler": {
                "enabled": False,
                "hour": 9,
                "minute": 15,
                "timezone": "Europe/Moscow",
            },
            "quiz": {
                "questions": [
                    {
                        "question": "Тестовый вопрос?",
                        "photo": None,
                        "options": ["Да", "Нет"],
                        "correct": 0,
                    }
                ]
            },
        }
        if overrides:
            data.update(overrides)
        path = root / "config" / "personalization.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    return writer
