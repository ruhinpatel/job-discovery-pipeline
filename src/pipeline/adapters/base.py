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

# Repo root is three levels up from this file (src/pipeline/adapters/base.py).
DEFAULT_RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"

# "2+ years", "3 yrs", "at least 4 years" -> the number before "year(s)/yr(s)".
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


# "0-2 years", "1 to 3 yrs" -> group 1 is the range's floor.
_RANGE_RE = re.compile(r"(\d+)\s*(?:-|to|–)\s*\d+\s*\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def parse_min_years(text: str) -> int:
    """Return the smallest 'N years' figure found in free text, else 0.

    An "A-B years" range counts as its floor A (the low end is what gates
    eligibility), not B.

    Smallest, not first or largest: postings often say "3+ years required,
    5+ years preferred", and the floor is what the experience gate cares about.
    """
    text = text or ""
    found = [int(m) for m in _RANGE_RE.findall(text)]
    # Strip ranges before the single-figure pass so "0-2 years" does not also yield 2.
    found += [int(m) for m in _YEARS_RE.findall(_RANGE_RE.sub(" ", text))]
    return min(found) if found else 0


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
