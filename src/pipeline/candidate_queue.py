"""Candidate queue.

Ties the dedup ledger and the fit scorer into one flow: drop postings whose
role is already resolved, score the survivors, and rank them. The pipeline
only orders the work; a person reads the queue and decides what to do with
each row. The suppressed count is reported alongside the queue so a reviewer
can see how much repeat work the ledger removed.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/ on sys.path, not src/, so the
    # `pipeline` package is not importable. Add src/ (tests get it from conftest.py).
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.ledger import DEFAULT_LEDGER_PATH, fingerprint, load_resolved_fingerprints
from pipeline.scorer import (
    DEFAULT_POSTINGS_PATH,
    DEFAULT_PROFILE_PATH,
    load_postings,
    load_profile,
    score_posting,
)


def build_queue(
    postings_path: Path = DEFAULT_POSTINGS_PATH,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> dict:
    """Return {"total", "suppressed_count", "queue", "suppressed"}.

    `queue` holds scored survivors, highest score first, each with its
    fingerprint and status="kept". `suppressed` holds the postings the ledger
    removed (unscored, status="suppressed"), so the dedup is auditable.
    """
    postings = load_postings(postings_path)
    profile = load_profile(profile_path)
    resolved = load_resolved_fingerprints(ledger_path)

    queue: list[dict] = []
    suppressed: list[dict] = []
    for p in postings:
        fp = fingerprint(p.get("company", ""), p.get("title", ""))
        if fp in resolved:
            suppressed.append({"company": p.get("company", ""), "title": p.get("title", ""),
                               "url": p.get("url", ""), "fingerprint": fp,
                               "status": "suppressed"})
        else:
            queue.append({**score_posting(p, profile), "fingerprint": fp, "status": "kept"})

    queue.sort(key=lambda r: r["score"], reverse=True)
    return {"total": len(postings), "suppressed_count": len(suppressed),
            "queue": queue, "suppressed": suppressed}


def format_queue(result: dict) -> str:
    lines = [f"{result['total']} postings | {result['suppressed_count']} suppressed as "
             f"already-resolved | {len(result['queue'])} in queue", ""]
    if result["queue"]:
        lines.append(f"{'#':>2}  {'Score':>5}  {'Company':<18} {'Title':<30} Matched skills")
        for i, r in enumerate(result["queue"], 1):
            skills = ", ".join(r["matched_skills"]) or "-"
            lines.append(f"{i:>2}  {r['score']:>5.1f}  {r['company']:<18} {r['title']:<30} "
                         f"{len(r['matched_skills'])} ({skills})")
    else:
        lines.append("Queue is empty.")
    return "\n".join(lines)


def main() -> None:
    print(format_queue(build_queue()))


if __name__ == "__main__":
    main()
