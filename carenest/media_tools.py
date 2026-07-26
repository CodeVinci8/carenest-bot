from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
EXPECTED_COUNTS = {"favorites": 15, "quiz": 5, "memories": 30}


class MediaArchiveError(ValueError):
    pass


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members: list[zipfile.ZipInfo] = []
    for member in archive.infolist():
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if member.is_dir():
            continue
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise MediaArchiveError("Архив содержит небезопасный путь.")
        if path.suffix.casefold() not in SUPPORTED_SUFFIXES:
            raise MediaArchiveError("Архив содержит неподдерживаемый файл.")
        members.append(member)
    return members


def _classify(members: list[zipfile.ZipInfo]) -> dict[str, list[zipfile.ZipInfo]]:
    folders: dict[str, list[zipfile.ZipInfo]] = {}
    for member in members:
        parts = PurePosixPath(member.filename.replace("\\", "/")).parts
        folders.setdefault(parts[-2], []).append(member)
    counts = Counter(len(items) for items in folders.values())
    if counts != Counter(EXPECTED_COUNTS.values()):
        raise MediaArchiveError("Ожидаются отдельные группы из 15, 5 и 30 фотографий.")
    by_count = {len(items): items for items in folders.values()}
    return {
        category: sorted(by_count[count], key=lambda item: item.filename.casefold())
        for category, count in EXPECTED_COUNTS.items()
    }


def prepare_media_archive(
    archive_path: Path,
    output_dir: Path,
    *,
    max_side: int = 1600,
    jpeg_quality: int = 86,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_items: list[dict[str, object]] = []
    with zipfile.ZipFile(archive_path) as archive:
        groups = _classify(_safe_members(archive))
        for category, members in groups.items():
            category_dir = output_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)
            for index, member in enumerate(members, start=1):
                with archive.open(member) as source:
                    payload = source.read()
                try:
                    with Image.open(io.BytesIO(payload)) as opened:
                        image = ImageOps.exif_transpose(opened).convert("RGB")
                        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                        target = category_dir / f"{category}-{index:03d}.jpg"
                        image.save(
                            target,
                            "JPEG",
                            quality=jpeg_quality,
                            optimize=True,
                            exif=b"",
                        )
                except (OSError, ValueError) as error:
                    raise MediaArchiveError(
                        "Один из файлов не является корректным изображением."
                    ) from error
                manifest_items.append(
                    {
                        "category": category,
                        "file": target.name,
                        "bytes": target.stat().st_size,
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    }
                )
    manifest: dict[str, object] = {
        "version": 1,
        "counts": {
            category: sum(item["category"] == category for item in manifest_items)
            for category in EXPECTED_COUNTS
        },
        "files": manifest_items,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
