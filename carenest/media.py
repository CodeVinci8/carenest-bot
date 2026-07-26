from __future__ import annotations

import logging
import random
from pathlib import Path

from carenest.database import WishlistDatabase

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
logger = logging.getLogger(__name__)


def choose_random_image(directory: Path, *, randomizer: random.Random | None = None) -> Path | None:
    try:
        images = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        ]
    except OSError as error:
        logger.warning("Не удалось прочитать папку с фотографиями: %s", error)
        return None
    if not images:
        return None
    chooser = randomizer or random
    return chooser.choice(images)


def choose_shuffled_image(
    directory: Path,
    database: WishlistDatabase,
    category: str,
    *,
    randomizer: random.Random | None = None,
) -> Path | None:
    try:
        images = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
        )
    except OSError:
        return None
    selected = database.next_media_name(
        category,
        [path.name for path in images],
        randomizer=randomizer,
    )
    return directory / selected if selected else None
