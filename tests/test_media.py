from pathlib import Path

from carenest.media import choose_random_image


def test_missing_media_directory_returns_none(tmp_path: Path) -> None:
    assert choose_random_image(tmp_path / "missing") is None


def test_empty_media_directory_returns_none(tmp_path: Path) -> None:
    directory = tmp_path / "media"
    directory.mkdir()

    assert choose_random_image(directory) is None
