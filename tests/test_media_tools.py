import io
import random
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from carenest.database import WishlistDatabase
from carenest.media_tools import MediaArchiveError, prepare_media_archive


def image_bytes() -> bytes:
    stream = io.BytesIO()
    image = Image.new("RGB", (32, 24), "blue")
    image.getexif()[0x010E] = "private metadata"
    image.save(stream, "JPEG", exif=image.getexif())
    return stream.getvalue()


def build_archive(path, *, traversal: bool = False) -> None:
    groups = {"one": 15, "two": 5, "three": 30}
    with zipfile.ZipFile(path, "w") as archive:
        for folder, count in groups.items():
            for index in range(count):
                name = f"root/{folder}/photo-{index:03d}.jpg"
                archive.writestr(name, image_bytes())
        if traversal:
            archive.writestr("../outside.jpg", image_bytes())


def test_media_archive_is_safe_optimized_and_has_no_exif(tmp_path) -> None:
    archive = tmp_path / "media.zip"
    output = tmp_path / "runtime" / "media"
    build_archive(archive)

    manifest = prepare_media_archive(archive, output)

    assert manifest["counts"] == {"favorites": 15, "quiz": 5, "memories": 30}
    files = list(output.glob("*/*.jpg"))
    assert len(files) == 50
    with Image.open(files[0]) as image:
        assert not image.getexif()


def test_zip_traversal_is_rejected(tmp_path) -> None:
    archive = tmp_path / "media.zip"
    build_archive(archive, traversal=True)

    with pytest.raises(MediaArchiveError, match="небезопасный"):
        prepare_media_archive(archive, tmp_path / "output")


def test_shuffle_bag_survives_restart_and_avoids_repeat(tmp_path) -> None:
    database = WishlistDatabase(tmp_path / "wishlist.db")
    database.initialize()
    available = ["a.jpg", "b.jpg", "c.jpg"]
    first = database.next_media_name("memories", available, randomizer=random.Random(1))
    reopened = WishlistDatabase(database.path)
    second = reopened.next_media_name("memories", available, randomizer=random.Random(1))

    assert first in available
    assert second in available
    assert first != second


def test_private_runtime_patterns_are_ignored() -> None:
    content = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "runtime/" in content
    assert "*.db" in content
