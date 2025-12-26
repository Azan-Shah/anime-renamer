from __future__ import annotations

import re

# Jellyfin docs warn these reserved characters cause problems in names.
INVALID_CHARS = '<>:"/\\|?*'

# Matches: S01E02 / s1e2
RE_SEASON_EP = re.compile(r"(?i)\bS(?P<season>\d{1,2})E(?P<ep>\d{1,3})\b")

# Matches: 1x02 / 01x002
RE_X = re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<ep>\d{1,3})\b")

# Matches: "Title - 01 ..." (common anime torrents)
RE_DASH_EP = re.compile(r"(?i)\s-\s(?P<ep>\d{1,3})(?:\s|$)")

# Matches: "...Code01..." (QualideaCode01 etc.)
# Groups:
# - title: leading letters
# - ep: 2-digit episode number
# - tail: optional trailing text
RE_GLUED_2DIGIT = re.compile(r"(?i)(?P<title>[a-z]+)(?P<ep>\d{2})(?P<tail>[a-z].*)?$")

# Treat these as "special" ONLY if we don't already see SxxEyy / 1x02 / "- 01".
SPECIAL_KEYWORDS = ("OVA", "OAD", "SPECIAL", "SP")

# Extras (OP/ED/PV/etc.) that Jellyfin expects under an extras folder.
DEFAULT_EXTRA_KEYWORDS = (
    "NCOP",
    "NCED",
    "OP",
    "ED",
    "OPENING",
    "ENDING",
    "CREDITLESS",
    "PV",
    "TRAILER",
    "CM",
    "PROMO",
    "TEASER",
)
