"""LinkedIn-alert-style adapter.

Raw shape: a flat JSON list of parsed alert-email entries with camelCase fields
(jobTitle, companyName, link, snippet, seniority). There is no structured
experience field, so years come from the snippet text first, falling back to
the coarse `seniority` label.
"""

from __future__ import annotations

import json
from typing import Any

from pipeline.adapters.base import SourceAdapter, as_bool, parse_min_years

# Fallback floors when the snippet states no explicit years.
_SENIORITY_FLOOR = {"internship": 0, "entry level": 0, "associate": 1, "mid-senior level": 4}


class LinkedInAlertsAdapter(SourceAdapter):
    source_name = "linkedin_alerts"
    raw_extension = "json"

    def fetch_raw(self) -> list[Any]:
        return json.loads(self.raw_path.read_text(encoding="utf-8"))

    def normalize(self, raw: list[Any]) -> list[dict]:
        out = []
        for r in raw:
            snippet = r.get("snippet", "")
            years = parse_min_years(snippet)
            if years == 0:
                years = _SENIORITY_FLOOR.get(r.get("seniority", "").strip().lower(), 0)
            out.append({
                "company": r["companyName"].strip(),
                "title": r["jobTitle"].strip(),
                "url": r["link"].strip(),
                "description": snippet.strip(),
                "min_years_experience": years,
                "location": r.get("location", "").strip(),
                "sponsorship_offered": as_bool(r.get("sponsorshipOffered"), True),
                "requires_clearance": as_bool(r.get("requiresClearance"), False),
                "referral": as_bool(r.get("referral"), False),
            })
        return out
