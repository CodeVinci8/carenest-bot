"""Regression guards for menu routing and the public showcase constraints.

Every reply-keyboard button must resolve to a registered handler (routing is
decoupled from visible labels), and the public bot must not expose the
relationship-counting scenario at all.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from carenest import handlers
from carenest.app import BOT_COMMANDS
from carenest.config import inspect_configuration
from carenest.database import WishlistDatabase
from carenest.handlers import (
    build_info_router,
    build_mood_router,
    build_quiz_router,
    build_start_router,
    build_wishlist_router,
)
from carenest.handlers.info import HELP_TEXT
from carenest.handlers.keyboards import get_main_keyboard

REPO_ROOT = Path(__file__).resolve().parent.parent


def _button_texts() -> list[str]:
    keyboard = get_main_keyboard()
    return [button.text for row in keyboard.keyboard for button in row]


def _text_resolves(router, text: str) -> bool:
    event = SimpleNamespace(text=text)
    for handler in router.message.handlers:
        for flt in handler.filters:
            callback = flt.callback
            if getattr(callback, "__name__", "") == "resolve":
                try:
                    if callback(event):
                        return True
                except Exception:
                    pass
    return False


def _routers(config, database):
    return [
        build_start_router(config),
        build_info_router(config),
        build_quiz_router(config),
        build_mood_router(config, database),
        build_wishlist_router(config, database),
    ]


def test_every_main_keyboard_button_reaches_a_handler(tmp_path, clean_environment) -> None:
    result = inspect_configuration(project_root=tmp_path, require_secrets=False)
    config = result.config
    assert config is not None
    database = WishlistDatabase(config.paths.database)
    database.initialize()
    routers = _routers(config, database)

    buttons = _button_texts()
    assert buttons, "main keyboard must expose buttons"
    for text in buttons:
        assert any(_text_resolves(router, text) for router in routers), (
            f"no handler routes the button {text!r}"
        )


def test_public_bot_has_no_relationship_scenario() -> None:
    # No /days command, no help entry, no button, no module, no router export.
    assert all(command.command != "days" for command in BOT_COMMANDS)
    assert "/days" not in HELP_TEXT
    assert not any("вместе" in text.lower() for text in _button_texts())

    import carenest.texts as texts

    assert not hasattr(texts, "RELATIONSHIP_BUTTON")
    assert not hasattr(handlers, "build_relationship_router")
    assert importlib.util.find_spec("carenest.handlers.relationship") is None


def test_public_example_has_no_relationship_date() -> None:
    data = json.loads((REPO_ROOT / "config" / "personalization.example.json").read_text("utf-8"))
    assert "relationship_start_date" not in data


def test_committed_example_quiz_keeps_five_rounds_of_four_answers() -> None:
    data = json.loads((REPO_ROOT / "config" / "personalization.example.json").read_text("utf-8"))
    questions = data["quiz"]["questions"]
    assert len(questions) == 5
    for question in questions:
        assert len(question["options"]) == 4


def test_gitignore_excludes_secrets_and_private_data() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text("utf-8")
    for needle in (".env", "personalization.json", "*.db", "runtime/"):
        assert needle in gitignore, f"{needle!r} must be git-ignored"
