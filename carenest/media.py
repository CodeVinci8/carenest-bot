from __future__ import annotations

import logging
import random
from pathlib import Path

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
