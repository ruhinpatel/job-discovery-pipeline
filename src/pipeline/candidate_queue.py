"""Candidate queue.

Ties the dedup ledger and the fit scorer into one flow: drop postings whose
role is already resolved, score the survivors, collapse in-batch reposts of
the same role to the best-scoring row, and rank them. The pipeline
only orders the work; a person reads the queue and decides what to do with
each row. A decision layer then runs on the scored rows: hard gates remove
ineligible postings, and surviving rows get a lane (the recommended effort).
The suppressed and gated counts are reported alongside the queue so a reviewer
can see how much work each stage removed.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/ on sys.path, not src/, so the
    # `pipeline` package is not importable. Add src/ (tests get it from conftest.py).
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.adapters.base import as_bool
from pipeline.gates import check_gates
from pipeline.lanes import assign_lane
from pipeline.llm_scorer import get_scorer
from pipeline.ledger import DEFAULT_LEDGER_PATH, fingerprint, load_resolved_fingerprints
from pipeline.scorer import (
    DEFAULT_POSTINGS_PATH,
    DEFAULT_PROFILE_PATH,
    load_postings,
    load_profile,
)


def build_queue(
    postings_path: Path = DEFAULT_POSTINGS_PATH,
    profile_path: Path = DEFAULT_PROFILE_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> dict:
    """Return {"total", "suppressed_count", "gated_count", "duplicate_count",
    "queue", "suppressed", "gated", "duplicates"}.

    Three distinct removals, in this order, kept separate so each is auditable:
    - `suppressed`: postings whose fingerprint is already in the resolved
      ledger (unscored, status="suppressed").
    - `gated`: scored postings that fail a hard eligibility gate (status="gated",
      with failed_gate and reason). Gated rows skip in-batch dedup, so a
      gated repost cannot displace an eligible row of the same role.
    - `duplicates`: unresolved reposts of a role already in this batch (same
      fingerprint, different URL). Only the highest-scoring row per
      fingerprint stays in `queue`; ties keep the first in input order.
    `queue` holds the deduped, scored survivors, highest score first, each
    with its fingerprint, status="kept", and lane / lane_name / lane_reason.
    Lane-0 survivors (low score, no referral) stay in the queue, flagged, so
    the full spread of recommendations is visible.
    """
    postings = load_postings(postings_path)
    profile = load_profile(profile_path)
    resolved = load_resolved_fingerprints(ledger_path)
    score_fn = get_scorer()

    by_url = {p.get("url", ""): p for p in postings}
    scored: list[dict] = []
    suppressed: list[dict] = []
    for p in postings:
        fp = fingerprint(p.get("company", ""), p.get("title", ""))
        if fp in resolved:
            suppressed.append({"company": p.get("company", ""), "title": p.get("title", ""),
                               "url": p.get("url", ""), "fingerprint": fp,
                               "status": "suppressed"})
        else:
            scored.append({**score_fn(p, profile), "fingerprint": fp, "status": "kept"})

    # Decision pass: gates remove ineligible rows; survivors get a lane.
    eligible: list[dict] = []
    gated: list[dict] = []
    for row in scored:
        posting = by_url[row["url"]]
        gate = check_gates(posting, profile)
        if not gate.passed:
            gated.append({"company": row["company"], "title": row["title"], "url": row["url"],
                          "fingerprint": row["fingerprint"], "score": row["score"],
                          "failed_gate": gate.failed_gate, "reason": gate.reason,
                          "status": "gated"})
            continue
        decision = assign_lane(gate, row["score"], as_bool(posting.get("referral"), False))
        eligible.append({**row, "lane": decision.lane, "lane_name": decision.name,
                         "lane_reason": decision.reason})
    scored = eligible

    # Within-batch dedup: strictly-greater comparison keeps the first row on ties.
    best: dict[str, dict] = {}
    for row in scored:
        cur = best.get(row["fingerprint"])
        if cur is None or row["score"] > cur["score"]:
            best[row["fingerprint"]] = row
    queue = [r for r in scored if best[r["fingerprint"]] is r]
    duplicates = [{"company": r["company"], "title": r["title"], "url": r["url"],
                   "fingerprint": r["fingerprint"], "status": "duplicate"}
                  for r in scored if best[r["fingerprint"]] is not r]

    queue.sort(key=lambda r: r["score"], reverse=True)
    return {"total": len(postings), "suppressed_count": len(suppressed),
            "gated_count": len(gated), "duplicate_count": len(duplicates), "queue": queue,
            "suppressed": suppressed, "gated": gated, "duplicates": duplicates}


def format_queue(result: dict) -> str:
    lines = [f"{result['total']} postings | {result['suppressed_count']} resolved-suppressed | "
             f"{result['gated_count']} gated | "
             f"{result['duplicate_count']} in-batch duplicates | {len(result['queue'])} in queue", ""]
    if result["queue"]:
        lines.append(f"{'#':>2}  {'Score':>5}  {'Lane':<14} {'Company':<18} {'Title':<30} "
                     "Matched skills")
        for i, r in enumerate(result["queue"], 1):
            skills = ", ".join(r["matched_skills"]) or "-"
            lane = f"{r['lane']} {r['lane_name']}"
            lines.append(f"{i:>2}  {r['score']:>5.1f}  {lane:<14} {r['company']:<18} "
                         f"{r['title']:<30} {len(r['matched_skills'])} ({skills})")
    else:
        lines.append("Queue is empty.")
    if result["gated"]:
        by_gate: dict[str, int] = {}
        for g in result["gated"]:
            by_gate[g["failed_gate"]] = by_gate.get(g["failed_gate"], 0) + 1
        lines += ["", "Gated out: " + ", ".join(f"{n} {gate}" for gate, n in sorted(by_gate.items()))]
    return "\n".join(lines)


def main() -> None:
    print(format_queue(build_queue()))


if __name__ == "__main__":
    main()
