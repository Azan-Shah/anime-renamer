from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml


@dataclass(frozen=True)
class Config:
    inbox_dir: Path
    dest_root: Path
    quarantine_dir: Path

    default_season: int
    specials_season: int

    allowed_ext: List[str]

    extras_dirname: str
    extras_map: Dict[str, str]  # keyword -> bucket folder name

    series_overrides: Dict[str, str]

    perplexity_enabled: bool
    perplexity_api_key: str
    perplexity_model: str


def _as_path(value: str | Path) -> Path:
    return Path(str(value)).expanduser()


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    paths = data.get("paths", {}) or {}
    rules = data.get("rules", {}) or {}
    series = data.get("series", {}) or {}
    perplexity = data.get("perplexity", {}) or {}

    inbox_dir = _as_path(paths["inbox_dir"])
    dest_root = _as_path(paths["dest_root"])
    quarantine_dir = _as_path(paths["quarantine_dir"])

    allowed_ext = [
        str(x).lower().lstrip(".")
        for x in (rules.get("allowed_ext", ["mkv", "mp4", "avi"]) or [])
    ]

    extras_map_raw = rules.get("extras_map", {}) or {}
    extras_map = {str(k).upper(): str(v) for k, v in extras_map_raw.items()}

    overrides_raw = series.get("overrides", {}) or {}
    overrides = {str(k): str(v) for k, v in overrides_raw.items()}

    return Config(
        inbox_dir=inbox_dir,
        dest_root=dest_root,
        quarantine_dir=quarantine_dir,
        default_season=int(rules.get("default_season", 1)),
        specials_season=int(rules.get("specials_season", 0)),
        allowed_ext=allowed_ext,
        extras_dirname=str(rules.get("extras_dirname", "extras")),
        extras_map=extras_map,
        series_overrides=overrides,
        perplexity_enabled=bool(perplexity.get("enabled", False)),
        perplexity_api_key=str(perplexity.get("api_key", "")),
        perplexity_model=str(perplexity.get("model", "")),
    )
