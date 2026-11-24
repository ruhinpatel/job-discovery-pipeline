"""Hard eligibility gates.

Gate versus score. The scorer (scorer.py) answers "how good a fit is this
posting?" and can only LOWER a score; a high-scoring role the candidate cannot
legally or practically take would still rank near the top. A gate answers a
different question, "is the candidate eligible at all?", and when it fails the
row is REMOVED from the queue no matter how well it scores. That is why
`min_yoe` here overlaps with the scorer's `_seniority_fit` on purpose: the
scorer nudges the rank, the gate decides whether the row is shown.

Gates run in a fixed order and the first failure wins, so the recorded reason
is deterministic and auditable:
    1. min_yoe             posting's stated floor is above the candidate's ceiling
    2. work_authorization  candidate needs sponsorship and the posting offers none
    3. clearance           posting requires clearance the candidate cannot obtain
    4. location            posting location is outside the candidate's allowed set

Missing data never disqualifies. Absent flags resolve to the permissive value
(sponsorship offered, no clearance, empty/unknown location, no allowed-location
list), so a source that does not report a field cannot silently gate a posting.

Pure functions, no I/O. Postings may be canonical dicts or rows read back from
postings.csv, where booleans arrive as "True"/"False" strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pipeline.adapters.base import as_bool

# Multi-location postings join places with "|" or ";" (e.g. Greenhouse).
_LOCATION_SPLIT_RE = re.compile(r"[|;]")
# Spelling variants that name the same place; applied after lowercasing.
_LOCATION_ALIASES = {"new york city, ny": "new york, ny", "new york city": "new york"}


def _norm_location(s: str) -> str:
    s = " ".join(s.lower().split())
    return _LOCATION_ALIASES.get(s, s)


def location_allowed(location: str, allowed: list[str]) -> bool:
    """True if ANY place in a (possibly multi-location) posting is allowed.

    A posting open in several places is eligible when one of them is, so the
    gate must not require the whole string to equal one allowed value.
    """
    allowed_set = {_norm_location(a) for a in allowed}
    parts = [_norm_location(p) for p in _LOCATION_SPLIT_RE.split(location) if p.strip()]
    return any(p in allowed_set for p in parts)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    failed_gate: str | None = None
    reason: str | None = None


_PASS = GateResult(passed=True)


def _fail(gate: str, reason: str) -> GateResult:
    return GateResult(passed=False, failed_gate=gate, reason=reason)


def check_gates(posting: dict[str, Any], profile: dict[str, Any]) -> GateResult:
    """Return the first failed gate for this posting, or a passing result."""
    floor = int(posting.get("min_years_experience", 0) or 0)
    ceiling = profile.get("max_years_experience")
    if ceiling is not None and floor > int(ceiling):
        return _fail("min_yoe", f"stated floor {floor}y above candidate ceiling {int(ceiling)}y")

    sponsorship_offered = as_bool(posting.get("sponsorship_offered"), True)
    if as_bool(profile.get("needs_sponsorship"), False) and not sponsorship_offered:
        return _fail("work_authorization", "no sponsorship offered")

    if (as_bool(posting.get("requires_clearance"), False)
            and not as_bool(profile.get("can_obtain_clearance"), True)):
        return _fail("clearance", "clearance required")

    location = (posting.get("location") or "").strip()
    allowed = profile.get("allowed_locations")
    if location and allowed is not None and not location_allowed(location, allowed):
        return _fail("location", f"location {location!r} not in candidate's allowed set")

    return _PASS
