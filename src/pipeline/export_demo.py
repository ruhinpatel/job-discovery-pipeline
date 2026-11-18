"""Demo export.

Runs the real pipeline over the synthetic demo data and writes the result as
a JS global (`window.DEMO_DATA = {...};`) for the static dashboard in docs/.
A JS file, not bare JSON, so docs/index.html can load it with a plain
<script src> tag: no fetch, no CORS problem from file:// or GitHub Pages, and
no network request of any kind. Every number on the page comes from this
export, so the dashboard cannot drift from what the code actually produces.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/ on sys.path, not src/.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.adapters.ingest import ALL_ADAPTERS
from pipeline.candidate_queue import build_queue
from pipeline.router import TASK_TIERS
from pipeline.scorer import load_postings

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "docs" / "demo_data.js"

DISCLAIMER = ("Synthetic demo data only. The pipeline ranks and orders work; "
              "a human reviews every output before anything is used.")


def build_export() -> dict:
    """Return the dashboard payload. Paths are anchored to the repo root so
    the export does not depend on the caller's working directory."""
    result = build_queue(REPO_ROOT / "data" / "postings.csv",
                         REPO_ROOT / "data" / "profile.json",
                         REPO_ROOT / "data" / "resolved_roles.csv")

    # Scored rows do not carry YOE; join it back from the postings by URL.
    years_by_url = {p["url"]: int(p.get("min_years_experience") or 0)
                    for p in load_postings(REPO_ROOT / "data" / "postings.csv")}

    queue = [{"rank": i, "score": r["score"], "company": r["company"], "title": r["title"],
              "matched_skills": list(r["matched_skills"]),
              "min_years_experience": years_by_url.get(r["url"], 0), "url": r["url"]}
             for i, r in enumerate(result["queue"], 1)]

    # Per-source counts come from each ingest adapter run, before dedup. They
    # sum to summary.total because data/postings.csv is the generated merge of
    # these same adapters (ingest.build_postings), not a separate dataset.
    sources = [{"name": cls().source_name, "count": len(cls().run())} for cls in ALL_ADAPTERS]

    routing = [{"task": task, "model_tier": entry["tier"], "note": entry["rationale"]}
               for task, entry in TASK_TIERS.items()]

    return {
        "disclaimer": DISCLAIMER,
        "summary": {"total": result["total"],
                    "resolved_suppressed": result["suppressed_count"],
                    "in_batch_duplicates": result["duplicate_count"],
                    "in_queue": len(result["queue"])},
        "queue": queue,
        "sources": sources,
        "routing_tiers": routing,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(build_export(), indent=2)
    OUTPUT_PATH.write_text(f"window.DEMO_DATA = {payload};\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
