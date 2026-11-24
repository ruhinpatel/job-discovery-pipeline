"""Source adapter interface.

Every discovery source (alert emails, ATS boards, curated lists, company career
pages) hands back data in its own shape. The rest of the pipeline (dedup ->
score -> rank) only understands one shape: the canonical posting, a dict with
exactly these keys:

    company (str), title (str), url (str), description (str),
    min_years_experience (int), location (str), sponsorship_offered (bool),
    requires_clearance (bool), referral (bool)

The last four feed the decision layer (gates, lanes). A source that lacks one
gets a safe default so a missing value never disqualifies a posting:
sponsorship_offered=True, requires_clearance=False, referral=False,
location="" (unknown).

A SourceAdapter isolates that mismatch. Each source gets one small subclass
that knows how to load its raw records (`fetch_raw`) and map them to the
canonical schema (`normalize`). Downstream code never sees a raw shape, so
adding a source means adding one adapter and nothing else.

IMPORTANT: in production, `fetch_raw` would call a live API or parse job-alert
emails. In this public project it instead reads a committed SYNTHETIC fixture
from `data/raw/`, so there are no network calls and no real postings or
personal data. All adapter output is a candidate list only: a human reviews it
before anything is acted on.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

CANONICAL_KEYS = ("company", "title", "url", "description", "min_years_experience",
                  "location", "sponsorship_offered", "requires_clearance", "referral")

from pipeline import config

DEFAULT_RAW_DIR = config.raw_dir(config.DEFAULT_DATA_DIR)

_WORD_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
              "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_NUM = r"\d+(?:\.\d+)?|" + "|".join(_WORD_NUMS)

# One "N years" figure. Forms: "3 years", "3+ years", "2 or more years",
# "three years", "five (5)+ years", "1.5 years", and ranges with -, en dash,
# em dash or "to" ("3-5 years", "three to five years"): `lo` is the floor.
_YEARS_RE = re.compile(
    rf"\b(?P<lo>{_NUM})(?:\s*\((?P<paren>\d+)\))?"
    rf"(?:\s*(?:[-–—]|\bto\b)\s*(?P<hi>{_NUM}))?"
    r"\s*(?:\+|or\s+(?:more|greater))?\s*(?:years?|yrs?)\b",
    re.IGNORECASE)
# "Years of experience: 4"
_LABEL_RE = re.compile(rf"\byears?\s+of\s+(?:relevant\s+)?experience\s*:\s*(?P<lo>{_NUM})\b",
                       re.IGNORECASE)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# (a) a sentence about the company, not the candidate. Two tiers:
# hard cues discard the sentence whatever else it says ("for over 20 years we ...").
_COMPANY_HARD_RE = re.compile(r"\b(?:for over|for more than|since|founded)\b", re.IGNORECASE)
# Soft cues discard it only when it states no requirement ("Our company is 12
# years old"), so "We require 5+ years of experience" and "8 years of experience
# at a public company" keep their figure.
_COMPANY_SOFT_RE = re.compile(r"\b(?:we|our|us|company)\b", re.IGNORECASE)
_STATES_REQUIREMENT = ("experience", "required", "requires", "minimum", "qualification",
                       "proficiency")
# (b) a time window ("within 1 year"), looked for in the three words before a match.
_WINDOW_RE = re.compile(r"\b(?:within|after|past|last|every|each|in the next|over the next)\b",
                        re.IGNORECASE)
# A sentence containing one of these is talking about what the role requires.
_REQUIREMENT_WORDS = ("experience", "required", "requires", "minimum", "qualification",
                      "proficiency", "years of")


def _years_value(m: re.Match) -> int:
    if m.groupdict().get("paren"):
        return int(m.group("paren"))
    lo = m.group("lo").lower()
    return _WORD_NUMS[lo] if lo in _WORD_NUMS else int(lo.split(".")[0])


def find_min_years(text: str | None) -> int | None:
    """Return the stated minimum years of experience, or None if none is stated.

    Heuristic, per sentence. Every "N years" figure is a candidate, except:
    - sentences about the company: always when they say "for over", "for more
      than", "since" or "founded"; when they say we/our/us/company only if
      they state no requirement (experience, required, minimum, ...); and
    - time windows ("within 1 year", "over the next 4 years").
    Of the rest, figures in a sentence that talks about requirements
    (experience, required, minimum, ...) win; the smallest is returned, since
    postings often say "3+ years required, 5+ years preferred" and the floor is
    what the experience gate cares about. A range "A-B years" counts as A.
    None (not found) differs from 0 (an explicit "0-2 years").
    """
    required: list[int] = []
    other: list[int] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text or ""):
        if not sentence.strip() or _COMPANY_HARD_RE.search(sentence):
            continue
        lowered = sentence.lower()
        if (_COMPANY_SOFT_RE.search(sentence)
                and not any(w in lowered for w in _STATES_REQUIREMENT)):
            continue
        is_requirement = any(w in lowered for w in _REQUIREMENT_WORDS)
        for regex in (_YEARS_RE, _LABEL_RE):
            for m in regex.finditer(sentence):
                if _WINDOW_RE.search(" ".join(sentence[:m.start()].split()[-3:])):
                    continue
                (required if is_requirement else other).append(_years_value(m))
    found = required or other
    return min(found) if found else None


def parse_min_years(text: str) -> int:
    """Stated minimum years, or 0 when none is found (see find_min_years)."""
    return find_min_years(text) or 0


def as_bool(value: Any, default: bool) -> bool:
    """Coerce a raw flag to bool, returning `default` when the source omitted it.

    Accepts real bools and the strings "true"/"false" (CSV-style). Anything
    else is treated as missing, so the caller's safe default applies.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return default


class SourceAdapter(ABC):
    """Load one source's raw records and normalize them to canonical postings."""

    #: Short identifier; also the fixture's basename in data/raw/.
    source_name: str = ""
    #: Fixture file extension (without dot), e.g. "json" or "csv".
    raw_extension: str = "json"

    def __init__(self, raw_dir: Path | None = None) -> None:
        self.raw_dir = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR

    @property
    def raw_path(self) -> Path:
        return self.raw_dir / f"{self.source_name}.{self.raw_extension}"

    @abstractmethod
    def fetch_raw(self) -> list[Any]:
        """Return this source's raw records, in the source's own shape."""

    @abstractmethod
    def normalize(self, raw: list[Any]) -> list[dict]:
        """Map raw records to canonical postings (see CANONICAL_KEYS)."""

    def run(self) -> list[dict]:
        """fetch_raw -> normalize."""
        return self.normalize(self.fetch_raw())
