from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .config import Config
from .perplexity_client import classify_media
from .rules import (
    DEFAULT_EXTRA_KEYWORDS,
    INVALID_CHARS,
    RE_DASH_EP,
    RE_GLUED_2DIGIT,
    RE_SEASON_EP,
    RE_X,
    SPECIAL_KEYWORDS,
)


@dataclass(frozen=True)
class Decision:
    # "episode" | "special" | "extra" | "ova" | "movie" | "unknown"
    kind: str
    series_name: str
    season: Optional[int]
    episode: Optional[int]
    extra_bucket: Optional[str]
    movie_title: Optional[str]
    movie_year: Optional[int]


def sanitize_name(name: str) -> str:
    s = str(name or "").strip()
    for ch in INVALID_CHARS:
        s = s.replace(ch, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Remove release/quality/group noise so the series folder name stays stable
_NOISE_PATTERNS = [
    r"\b(480p|720p|1080p|2160p|4k)\b",
    r"\b(10bit|8bit|hdr10\+?|hdr|dv|dolby\.?vision)\b",
    r"\b(x264|x265|h\.?264|h\.?265|hevc|avc)\b",
    r"\b(aac|flac|opus|dts|truehd|ddp|eac3|ac3)\b",
    r"\b(web-?dl|webrip|web|bluray|bdrip|brrip|remux|dvd|dvdrip|hdrip)\b",
    r"\b(dual\s*audio|multi\s*audio|subbed|dubbed)\b",
    r"\b(repack|proper|uncensored)\b",
    r"\b(batch)\b",
    r"\b(s\d{1,2})\b",
    r"\b(season\s*\d{1,2})\b",
    r"\b(complete)\b",
]
_BRACKETED = re.compile(r"[\[\(].*?[\]\)]")


def normalize_series_title(raw: str) -> str:
    s = str(raw or "").strip()

    # remove [SubsPlease] / (1080p) / etc.
    s = _BRACKETED.sub(" ", s)

    # unify separators
    s = s.replace(".", " ").replace("_", " ").replace("-", " ")

    # remove noise tokens
    for pat in _NOISE_PATTERNS:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)

    s = sanitize_name(s)
    if len(s) < 2:
        s = sanitize_name(raw)
    return s


def choose_series_name(raw_series: str, cfg: Config) -> str:
    cleaned = normalize_series_title(raw_series)
    for k, v in cfg.series_overrides.items():
        if k.lower() in cleaned.lower():
            return sanitize_name(v)
    return cleaned


def infer_series_from_context(file_path: Path) -> str:
    return file_path.parent.name


def classify_kind(filename: str) -> str:
    """
    IMPORTANT RULE:
    If it looks like a real episode number (S01E02, 1x02, or ' - 02 '),
    always treat it as an episode. This prevents OP/ED/SP keywords in the
    filename from pushing real episodes into specials/extras.
    """
    stem = Path(filename).stem
    if RE_SEASON_EP.search(stem) or RE_X.search(stem) or RE_DASH_EP.search(stem):
        return "episode"

    up = filename.upper()
    if any(k in up for k in SPECIAL_KEYWORDS):
        return "special"
    if any(k in up for k in DEFAULT_EXTRA_KEYWORDS):
        return "extra"
    return "episode"


def parse_season_episode(stem: str, default_season: int) -> Tuple[Optional[int], Optional[int]]:
    m = RE_SEASON_EP.search(stem)
    if m:
        return int(m.group("season")), int(m.group("ep"))

    m = RE_X.search(stem)
    if m:
        return int(m.group("season")), int(m.group("ep"))

    m = RE_DASH_EP.search(stem)
    if m:
        return default_season, int(m.group("ep"))

    m = RE_GLUED_2DIGIT.match(stem.replace(".", ""))
    if m:
        ep = int(m.group("ep"))
        if 1 <= ep <= 99:
            return default_season, ep

    # last resort: any trailing number
    m = re.search(r"(?P<ep>\d{1,3})(?!\d)", stem)
    if m:
        ep = int(m.group("ep"))
        if 1 <= ep <= 400:
            return default_season, ep

    return None, None


def decide_extra_bucket(filename: str, cfg: Config) -> str:
    up = filename.upper()
    for key, bucket in cfg.extras_map.items():
        if key in up:
            return bucket
    return "other"


def _local_decision(path: Path, cfg: Config, series_name: str) -> Decision:
    kind = classify_kind(path.name)

    season: Optional[int] = None
    ep: Optional[int] = None
    bucket: Optional[str] = None

    if kind == "episode":
        season, ep = parse_season_episode(path.stem, cfg.default_season)
        if season is None or ep is None:
            kind = "unknown"

    if kind == "extra":
        bucket = decide_extra_bucket(path.name, cfg)

    return Decision(
        kind=kind,
        series_name=series_name,
        season=season,
        episode=ep,
        extra_bucket=bucket,
        movie_title=None,
        movie_year=None,
    )


def make_decision(path: Path, cfg: Config) -> Decision:
    # Always do local parsing first (fast, deterministic)
    raw_series_local = infer_series_from_context(path)
    series_name_local = choose_series_name(raw_series_local, cfg)
    base = _local_decision(path, cfg, series_name_local)

    if not cfg.perplexity_enabled:
        return base

    # API enhances series naming and helps with ova/movie detection.
    try:
        d = classify_media(cfg, path)
    except Exception:
        return base

    raw_series_api = d.series or raw_series_local
    series_name = choose_series_name(raw_series_api, cfg)

    api_kind = (d.kind or "unknown").strip().lower()
    if api_kind not in {"episode", "ova", "special", "extra", "movie", "unknown"}:
        api_kind = "unknown"

    # If API is unknown, never force quarantine: keep local decision but use improved series_name
    if api_kind == "unknown":
        return Decision(
            kind=base.kind,
            series_name=series_name,
            season=base.season,
            episode=base.episode,
            extra_bucket=base.extra_bucket,
            movie_title=None,
            movie_year=None,
        )

    # Prefer local numbering for normal content if local already parsed it
    if base.kind in {"episode", "extra", "special"}:
        return Decision(
            kind=base.kind,
            series_name=series_name,
            season=base.season,
            episode=base.episode,
            extra_bucket=base.extra_bucket,
            movie_title=None,
            movie_year=None,
        )

    # Accept API for ova/movie when local couldn't reliably decide
    if api_kind == "ova":
        ova_no = int(d.episode) if d.episode is not None else None
        if ova_no is None:
            return Decision(
                kind="unknown",
                series_name=series_name,
                season=None,
                episode=None,
                extra_bucket=None,
                movie_title=None,
                movie_year=None,
            )
        return Decision(
            kind="ova",
            series_name=series_name,
            season=None,
            episode=ova_no,
            extra_bucket=None,
            movie_title=None,
            movie_year=None,
        )

    if api_kind == "movie":
        title = normalize_series_title(d.title or "")
        year = int(d.year) if d.year is not None else None
        if not title or year is None:
            return Decision(
                kind="unknown",
                series_name=series_name,
                season=None,
                episode=None,
                extra_bucket=None,
                movie_title=None,
                movie_year=None,
            )
        return Decision(
            kind="movie",
            series_name=series_name,
            season=None,
            episode=None,
            extra_bucket=None,
            movie_title=title,
            movie_year=year,
        )

    # If API says episode and provides episode number, accept it
    if api_kind == "episode":
        season = int(d.season) if d.season is not None else cfg.default_season
        ep = int(d.episode) if d.episode is not None else None
        if ep is None:
            return Decision(
                kind="unknown",
                series_name=series_name,
                season=None,
                episode=None,
                extra_bucket=None,
                movie_title=None,
                movie_year=None,
            )
        return Decision(
            kind="episode",
            series_name=series_name,
            season=season,
            episode=ep,
            extra_bucket=None,
            movie_title=None,
            movie_year=None,
        )

    if api_kind == "extra":
        bucket = (d.extra_bucket or "").strip().lower() or decide_extra_bucket(path.name, cfg)
        return Decision(
            kind="extra",
            series_name=series_name,
            season=None,
            episode=None,
            extra_bucket=bucket,
            movie_title=None,
            movie_year=None,
        )

    if api_kind == "special":
        return Decision(
            kind="special",
            series_name=series_name,
            season=None,
            episode=None,
            extra_bucket=None,
            movie_title=None,
            movie_year=None,
        )

    return base
