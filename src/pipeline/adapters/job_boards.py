"""Greenhouse/Lever-style job-board adapter.

Raw shape: {"jobs": [{"title", "company": {"name"}, "absolute_url", "content",
"metadata": [{"name", "value"}]}]}. Company is nested and experience lives in a
name/value metadata list (key "yoe"), which is the most reliable source; the
content text is only a fallback.
"""

from __future__ import annotations

import json
from typing import Any

from pipeline.adapters.base import SourceAdapter, as_bool, parse_min_years


class JobBoardsAdapter(SourceAdapter):
    source_name = "job_boards"
    raw_extension = "json"

    def fetch_raw(self) -> list[Any]:
        return json.loads(self.raw_path.read_text(encoding="utf-8"))["jobs"]

    @staticmethod
    def _metadata_years(job: dict) -> int | None:
        for item in job.get("metadata") or []:
            if item.get("name", "").lower() == "yoe":
                try:
                    return int(str(item["value"]).strip())
                except (ValueError, TypeError):
                    return None  # malformed value: fall back to the text
        return None

    def normalize(self, raw: list[Any]) -> list[dict]:
        out = []
        for job in raw:
            years = self._metadata_years(job)
            if years is None:
                years = parse_min_years(job.get("content", ""))
            out.append({
                "company": job["company"]["name"].strip(),
                "title": job["title"].strip(),
                "url": job["absolute_url"].strip(),
                "description": job.get("content", "").strip(),
                "min_years_experience": years,
                "location": job.get("location", "").strip(),
                "sponsorship_offered": as_bool(job.get("sponsorship_offered"), True),
                "requires_clearance": as_bool(job.get("requires_clearance"), False),
                "referral": as_bool(job.get("referral"), False),
            })
        return out
