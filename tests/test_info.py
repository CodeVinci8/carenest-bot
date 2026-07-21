from carenest import __version__
from carenest.app import BOT_COMMANDS
from carenest.handlers.info import HELP_TEXT, about_text


def test_help_mentions_registered_real_commands() -> None:
    registered = {command.command for command in BOT_COMMANDS}

    assert registered == {
        "start",
        "quiz",
        "mood",
        "days",
        "wish",
        "wishlist",
        "cancel",
        "help",
        "about",
    }
    for command in registered:
        assert f"/{command}" in HELP_TEXT or command == "about"


def test_about_contains_name_and_current_version() -> None:
    text = about_text()

    assert "CareNest Bot" in text
    assert __version__ == "1.1.0"
    assert "Версия 1.1.0" in text
