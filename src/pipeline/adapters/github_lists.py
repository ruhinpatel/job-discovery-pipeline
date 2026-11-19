"""Curated GitHub list adapter (SimplifyJobs-style CSV).

Raw shape: CSV with columns company, role, application_link, notes,
sponsorship. There is no description column, so `notes` plus the sponsorship
flag are folded into the canonical description (the scorer reads that text).
Years are parsed from the notes. The sponsorship column maps to
sponsorship_offered: only an explicit "Does Not Offer" is False; "Offers" and
"Unknown" (and blank) are True, so an unknown never auto-disqualifies.
"""

from __future__ import annotations

import csv
from typing import Any

from pipeline.adapters.base import SourceAdapter, as_bool, parse_min_years


class GithubListsAdapter(SourceAdapter):
    source_name = "github_lists"
    raw_extension = "csv"

    def fetch_raw(self) -> list[Any]:
        with self.raw_path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def normalize(self, raw: list[Any]) -> list[dict]:
        out = []
        for row in raw:
            notes = row.get("notes", "").strip()
            sponsorship = row.get("sponsorship", "").strip()
            description = notes
            if sponsorship:
                description = f"{notes} Sponsorship: {sponsorship}.".strip()
            out.append({
                "company": row["company"].strip(),
                "title": row["role"].strip(),
                "url": row["application_link"].strip(),
                "description": description,
                "min_years_experience": parse_min_years(notes),
                "location": row.get("location", "").strip(),
                "sponsorship_offered": not sponsorship.lower().startswith("does not"),
                "requires_clearance": as_bool(row.get("requires_clearance"), False),
                "referral": as_bool(row.get("referral"), False),
            })
        return out
