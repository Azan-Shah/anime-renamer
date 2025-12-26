from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .config import Config


@dataclass(frozen=True)
class APIDecision:
    # "episode" | "ova" | "special" | "extra" | "movie" | "unknown"
    kind: str
    series: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    title: Optional[str] = None  # episode title or movie title
    year: Optional[int] = None   # for movies
    extra_bucket: Optional[str] = None  # "trailers"|"other"|"extras"


# -------------------------
# Caching helpers
# -------------------------

def _cache_path(cfg: Config) -> Path:
    return Path("api-cache.jsonl")


def _cache_key(file_path: Path) -> str:
    st = file_path.stat()
    return f"{file_path}|{st.st_size}|{int(st.st_mtime)}"


def _read_cache(cfg: Config) -> Dict[str, Dict[str, Any]]:
    p = _cache_path(cfg)
    if not p.exists():
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        # If key appears multiple times, keep the latest record
        out[rec["key"]] = rec["value"]
    return out


def _append_cache(cfg: Config, key: str, value: Dict[str, Any]) -> None:
    p = _cache_path(cfg)
    rec = {"key": key, "value": value}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _pplx_call(cfg: Config, prompt: str) -> str:
    api_key = cfg.perplexity_api_key or os.environ.get("PPLX_API_KEY", "")
    if not api_key:
        raise RuntimeError("Perplexity API key missing (config.perplexity.api_key or PPLX_API_KEY).")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": cfg.perplexity_model or "sonar",
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON. No markdown. No extra text."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def _loads_json_maybe_wrapped(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("Model did not return valid JSON.")


# -------------------------
# NEW: folder-level memory cache per run
# -------------------------

# Maps "folder path string" -> "best series string"
_FOLDER_SERIES_CACHE: Dict[str, str] = {}

# Optional call limiter for one Python run
_CALL_COUNT = 0


def _get_max_calls(cfg: Config) -> int:
    # If your Config doesn’t have this, default to unlimited (-1).
    # You can later add it properly to config.py if you want.
    return int(getattr(cfg, "perplexity_max_calls", -1) or -1)


def classify_media(cfg: Config, file_path: Path) -> APIDecision:
    """
    Classification with 3 layers:
    1) File cache from api-cache.jsonl (existing behavior).
    2) NEW: Folder-series cache: reuse series for other files in same folder.
    3) API call as last resort.
    """
    global _CALL_COUNT

    cache = _read_cache(cfg)
    key = _cache_key(file_path)

    # 1) File-level cache hit
    if key in cache:
        return APIDecision(**cache[key])

    # 2) Folder-level reuse (big credit saver for episode batches)
    folder_key = str(file_path.parent.resolve())
    if folder_key in _FOLDER_SERIES_CACHE:
        # We still need to classify kind; but to save credits we keep it conservative.
        # Return unknown kind but with series set; parse.py will still normalize and
        # planner can quarantine unknowns safely.
        return APIDecision(kind="unknown", series=_FOLDER_SERIES_CACHE[folder_key])

    # 3) Optional max call limiter
    max_calls = _get_max_calls(cfg)
    if max_calls == 0:
        raise RuntimeError("Perplexity disabled by perplexity_max_calls=0.")
    if max_calls > 0 and _CALL_COUNT >= max_calls:
        raise RuntimeError(f"Perplexity API call limit reached ({max_calls}).")

    parent_folder = file_path.parent.name
    filename = file_path.name

    prompt = f"""
You are classifying anime media files for a Jellyfin library.

Target library layout rules (must match):
- Episodes go to: Series/Season 01/Series - S01E01.ext
- OVAs go to: Series/OVA/Series - OVA01.ext
- Movies go to: Movies/Title (Year)/Title (Year).ext
- Extras (NCOP/NCED/OP/ED/PV/TRAILER) go to: Series/extras/<bucket>/...

Strict requirements:
- Return ONLY JSON (no text).
- "series" must be the canonical anime title ONLY (no resolution, no release group, no codec, no WEB-DL, no bracket tags).
- If kind="episode": must include series, season (int), episode (int).
- If kind="ova": must include series, episode (int) as OVA number; season must be null or omitted.
- If kind="movie": must include title (string) and year (int). If year is unknown, set kind="unknown".
- If kind="extra": must include extra_bucket as one of: trailers, other, extras.
- If unsure, use kind="unknown" (do NOT guess).

Return JSON keys exactly:
kind, series, season, episode, title, year, extra_bucket

Input:
folder="{parent_folder}"
filename="{filename}"
full_path="{str(file_path)}"
""".strip()

    raw = _pplx_call(cfg, prompt)
    _CALL_COUNT += 1

    value = _loads_json_maybe_wrapped(raw)

    if value.get("extra_bucket"):
        value["extra_bucket"] = str(value["extra_bucket"]).strip().lower()

    _append_cache(cfg, key, value)

    # NEW: If the API gave a series, remember it for whole folder (credit saver)
    series = value.get("series")
    if isinstance(series, str) and series.strip():
        _FOLDER_SERIES_CACHE[folder_key] = series.strip()

    time.sleep(0.2)
    return APIDecision(**value)
