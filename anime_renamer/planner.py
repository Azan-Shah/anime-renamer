from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .parse import Decision, sanitize_name


@dataclass(frozen=True)
class Operation:
    src: Path
    dst: Path
    kind: str  # "move"


def season_dirname(season: int) -> str:
    return f"Season {season:02d}"


def episode_filename(series: str, season: int, ep: int, ext: str) -> str:
    s = sanitize_name(series)
    return f"{s} - S{season:02d}E{ep:02d}{ext}"


def ova_filename(series: str, ova_no: int, ext: str) -> str:
    s = sanitize_name(series)
    return f"{s} - OVA{ova_no:02d}{ext}"


def movie_dirname(title: str, year: int) -> str:
    t = sanitize_name(title)
    return f"{t} ({year})"


def movie_filename(title: str, year: int, ext: str) -> str:
    t = sanitize_name(title)
    return f"{t} ({year}){ext}"


def build_destination(dec: Decision, cfg: Config, src: Path) -> Path:
    # Movies: OUTPUT/Movies/Title (Year)/Title (Year).ext
    if dec.kind == "movie" and dec.movie_title and dec.movie_year is not None:
        movies_root = cfg.dest_root / "Movies"
        return (
            movies_root
            / movie_dirname(dec.movie_title, dec.movie_year)
            / movie_filename(dec.movie_title, dec.movie_year, src.suffix)
        )

    # Everything else uses series root
    series_dir = cfg.dest_root / sanitize_name(dec.series_name)

    # Episodes: Series/Season 01/Series - S01E01.ext
    if dec.kind == "episode" and dec.season is not None and dec.episode is not None:
        return (
            series_dir
            / season_dirname(dec.season)
            / episode_filename(dec.series_name, dec.season, dec.episode, src.suffix)
        )

    # OVA: Series/OVA/Series - OVA01.ext
    if dec.kind == "ova":
        ova_no = dec.episode if dec.episode is not None else 1
        return series_dir / "OVA" / ova_filename(dec.series_name, ova_no, src.suffix)

    # Specials: Series/Season 00/<Series> - <original stem>.ext
    if dec.kind == "special":
        return (
            series_dir
            / season_dirname(cfg.specials_season)
            / f"{sanitize_name(dec.series_name)} - {sanitize_name(src.stem)}{src.suffix}"
        )

    # Extras: Series/extras/<bucket>/<Series> - <original stem>.ext
    if dec.kind == "extra":
        bucket = dec.extra_bucket or "other"
        return (
            series_dir
            / cfg.extras_dirname
            / sanitize_name(bucket)
            / f"{sanitize_name(dec.series_name)} - {sanitize_name(src.stem)}{src.suffix}"
        )

    # Unknown: quarantine
    return cfg.quarantine_dir / src.name


def make_operation(dec: Decision, cfg: Config, src: Path) -> Operation:
    return Operation(src=src, dst=build_destination(dec, cfg, src), kind="move")
