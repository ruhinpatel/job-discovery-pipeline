"""Company career-page adapter (ATS JSON feed).

Raw shape: {"company", "postings": [{"name", "categories": {"team"},
"hostedUrl", "descriptionPlain"}]}. Individual postings carry no company field
(the feed belongs to one employer), so the company comes from the feed-level
`company` key. Years are parsed from descriptionPlain.
"""

from __future__ import annotations

import json
from typing import Any

from pipeline.adapters.base import SourceAdapter, as_bool, parse_min_years


class CompanyCareersAdapter(SourceAdapter):
    source_name = "company_careers"
    raw_extension = "json"

    def fetch_raw(self) -> list[Any]:
        data = json.loads(self.raw_path.read_text(encoding="utf-8"))
        company = data.get("company", "")
        # Attach the feed-level employer to each record so normalize() is per-record.
        return [{**p, "_company": company} for p in data["postings"]]

    def normalize(self, raw: list[Any]) -> list[dict]:
        out = []
        for p in raw:
            desc = p.get("descriptionPlain", "").strip()
            team = (p.get("categories") or {}).get("team", "")
            if team:
                desc = f"Team: {team}. {desc}"
            out.append({
                "company": p["_company"].strip(),
                "title": p["name"].strip(),
                "url": p["hostedUrl"].strip(),
                "description": desc,
                "min_years_experience": parse_min_years(p.get("descriptionPlain", "")),
                "location": p.get("location", "").strip(),
                "sponsorship_offered": as_bool(p.get("sponsorshipOffered"), True),
                "requires_clearance": as_bool(p.get("requiresClearance"), False),
                "referral": as_bool(p.get("referral"), False),
            })
        return out
