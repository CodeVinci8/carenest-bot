from pathlib import Path

import pytest

from carenest.database import WishlistDatabase
from carenest.handlers.wishlist import (
    cancel_wishlist_input,
    delete_callback_item,
    display_wishlist_item,
    get_confirmation_keyboard,
    normalize_wishlist_item,
    verify_callback_item,
    wishlist_fingerprint,
)


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


def make_database(tmp_path: Path) -> WishlistDatabase:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    return database


def test_wishlist_deletion_requires_matching_confirmation(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    item_id = database.add_item("Книга")
    fingerprint = wishlist_fingerprint("Книга")

    assert verify_callback_item(database, item_id, fingerprint) == ("ready", "Книга")
    assert delete_callback_item(database, item_id, fingerprint) == "deleted"
    assert database.get_item(item_id) is None
    assert delete_callback_item(database, item_id, fingerprint) == "missing"


def test_confirmation_keyboard_has_delete_and_cancel_actions() -> None:
    keyboard = get_confirmation_keyboard(5, wishlist_fingerprint("Книга"))

    buttons = keyboard.inline_keyboard[0]
    assert [button.text for button in buttons] == ["Удалить", "Отмена"]
    assert ":confirm:" in buttons[0].callback_data
    assert ":cancel:" in buttons[1].callback_data


def test_stale_callback_does_not_delete_reused_id(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    item_id = database.add_item("Старое желание")
    stale_fingerprint = wishlist_fingerprint("Старое желание")
    assert database.delete_item(item_id, "Старое желание")
    reused_id = database.add_item("Новое желание")
    assert reused_id == item_id

    result = delete_callback_item(database, item_id, stale_fingerprint)

    assert result == "stale"
    assert database.get_item(item_id) == (item_id, "Новое желание")


def test_wishlist_input_normalizes_surrounding_whitespace() -> None:
    assert normalize_wishlist_item("  Новая книга \n") == "Новая книга"
    assert normalize_wishlist_item("   ") == ""


def test_legacy_long_item_is_safely_shortened_for_telegram() -> None:
    legacy_name = "я" * 1000

    displayed = display_wishlist_item(legacy_name)

    assert len(displayed) == 500
    assert displayed.endswith("…")


@pytest.mark.asyncio
async def test_cancel_clears_wishlist_input_state() -> None:
    state = FakeState()
    message = FakeMessage()

    await cancel_wishlist_input(message, state)

    assert state.cleared is True
    assert message.answers == ["Добавление желания отменено."]
