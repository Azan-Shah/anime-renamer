from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .config import Config


@dataclass(frozen=True)
class MediaFile:
    path: Path


def iter_media_files(cfg: Config) -> Iterable[MediaFile]:
    allowed = {"." + ext.lower().lstrip(".") for ext in cfg.allowed_ext}

    for p in cfg.inbox_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in allowed:
            yield MediaFile(path=p)


def list_media_files(cfg: Config) -> List[MediaFile]:
    return sorted(iter_media_files(cfg), key=lambda m: str(m.path).lower())
