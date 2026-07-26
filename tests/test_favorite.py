from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from carenest.database import WishlistDatabase
from carenest.handlers.mood import send_shuffled_photo
from carenest.texts import FAVORITE_FALLBACK_TEXT, FAVORITE_TEXT, SUPPORT_TEXT


def _make_images(directory: Path, count: int, prefix: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        stream = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(stream, "JPEG")
        (directory / f"{prefix}-{index:02d}.jpg").write_bytes(stream.getvalue())


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.photo_captions: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def answer_photo(self, photo, caption: str, **kwargs) -> None:
        self.photo_captions.append(caption)


def test_favorite_and_memory_pools_are_independent(tmp_path: Path) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    favorites = [f"fav-{i}.jpg" for i in range(15)]
    memories = [f"mem-{i}.jpg" for i in range(30)]

    fav_pick = database.next_media_name("favorites", favorites)
    mem_pick = database.next_media_name("mood", memories)

    assert fav_pick in favorites
    assert mem_pick in memories
    # Consuming the favourites bag must not touch the memories bag and vice versa.
    fav_seen = {fav_pick}
    for _ in range(len(favorites) - 1):
        fav_seen.add(database.next_media_name("favorites", favorites))
    assert fav_seen == set(favorites)
    # The memory bag still has (30 - 1) unshown items left.
    mem_seen = {mem_pick}
    for _ in range(len(memories) - 1):
        mem_seen.add(database.next_media_name("mood", memories))
    assert mem_seen == set(memories)


def test_favorite_shuffle_persists_and_no_repeat_until_pool_exhausted(
    tmp_path: Path,
) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    favorites = [f"fav-{i}.jpg" for i in range(15)]

    seen: list[str] = []
    for _ in range(len(favorites)):
        # Reopen each round to prove the bag survives a restart.
        reopened = WishlistDatabase(database.path)
        seen.append(reopened.next_media_name("favorites", favorites))

    assert sorted(seen) == sorted(favorites)  # every favourite shown once, no repeats


@pytest.mark.asyncio
async def test_favorite_handler_reads_favorites_not_memories(tmp_path: Path) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    favorites_dir = tmp_path / "media" / "favorites"
    _make_images(favorites_dir, 3, "fav")
    message = FakeMessage()

    await send_shuffled_photo(
        message, database, favorites_dir, "favorites", FAVORITE_TEXT, FAVORITE_FALLBACK_TEXT
    )

    assert message.photo_captions == [FAVORITE_TEXT]
    assert message.answers == []


@pytest.mark.asyncio
async def test_mood_handler_uses_text_fallback_when_directory_missing(
    tmp_path: Path,
) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    message = FakeMessage()

    await send_shuffled_photo(
        message, database, tmp_path / "missing", "mood", SUPPORT_TEXT, SUPPORT_TEXT
    )

    assert message.answers == [SUPPORT_TEXT]
    assert message.photo_captions == []


@pytest.mark.asyncio
async def test_favorite_handler_falls_back_when_pool_empty(tmp_path: Path) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    empty_dir = tmp_path / "media" / "favorites"
    empty_dir.mkdir(parents=True)
    message = FakeMessage()

    await send_shuffled_photo(
        message, database, empty_dir, "favorites", FAVORITE_TEXT, FAVORITE_FALLBACK_TEXT
    )

    assert message.answers == [FAVORITE_FALLBACK_TEXT]
    assert message.photo_captions == []
