"""Candidate queue.

Ties the dedup ledger and the fit scorer into one flow: drop postings whose
role is already resolved, score the survivors, collapse in-batch reposts of
the same role to the best row (referral first, then score), and rank them. The pipeline
only orders the work; a person reads the queue and decides what to do with
each row. A decision layer then runs on the scored rows: hard gates remove
ineligible postings, and surviving rows get a lane (the recommended effort).
The suppressed and gated counts are reported alongside the queue so a reviewer
can see how much work each stage removed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/ on sys.path, not src/, so the
    # `pipeline` package is not importable. Add src/ (tests get it from conftest.py).
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import config
from pipeline.adapters.base import as_bool
from pipeline.adapters.greenhouse_live import GreenhouseLiveAdapter
from pipeline.adapters.ingest import write_postings
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
      fingerprint, different URL). Only one row per fingerprint
      stays in `queue`: a referral row beats a non-referral one, then the
      highest score wins; ties keep the first in input order.
    `queue` holds the deduped, scored survivors, highest score first, each
    with its fingerprint, status="kept", and lane / lane_name / lane_reason.
    Lane-0 survivors (low score, no referral) stay in the queue, flagged, so
    the full spread of recommendations is visible.
    """
    postings = load_postings(postings_path)
    profile = load_profile(profile_path)
    resolved = load_resolved_fingerprints(ledger_path)
    score_fn = get_scorer()

    # Each scored row travels with its own posting: URLs can repeat or be
    # empty, so rejoining by URL would gate a row on another row's data.
    scored: list[tuple[dict, dict]] = []
    suppressed: list[dict] = []
    for p in postings:
        fp = fingerprint(p.get("company", ""), p.get("title", ""))
        if fp in resolved:
            suppressed.append({"company": p.get("company", ""), "title": p.get("title", ""),
                               "url": p.get("url", ""), "fingerprint": fp,
                               "status": "suppressed"})
        else:
            scored.append((p, {**score_fn(p, profile), "fingerprint": fp, "status": "kept"}))

    # Decision pass: gates remove ineligible rows; survivors get a lane.
    eligible: list[dict] = []
    gated: list[dict] = []
    for posting, row in scored:
        gate = check_gates(posting, profile)
        if not gate.passed:
            gated.append({"company": row["company"], "title": row["title"], "url": row["url"],
                          "fingerprint": row["fingerprint"], "score": row["score"],
                          "failed_gate": gate.failed_gate, "reason": gate.reason,
                          "status": "gated"})
            continue
        referral = as_bool(posting.get("referral"), False)
        decision = assign_lane(gate, row["score"], referral)
        eligible.append({**row, "lane": decision.lane, "lane_name": decision.name,
                         "lane_reason": decision.reason, "referral": referral,
                         "min_years_experience": int(posting.get("min_years_experience") or 0)})
    scored = eligible

    # Within-batch dedup: a referral row beats any non-referral repost (it
    # bypasses the keyword screen), then higher score wins. Strictly-greater
    # comparison keeps the first row on ties.
    best: dict[str, dict] = {}
    for row in scored:
        cur = best.get(row["fingerprint"])
        if cur is None or (row["referral"], row["score"]) > (cur["referral"], cur["score"]):
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
                     f"{'Matched skills':<60} Why")
        for i, r in enumerate(result["queue"], 1):
            skills = ", ".join(r["matched_skills"]) or "-"
            lane = f"{r['lane']} {r['lane_name']}"
            matched = f"{len(r['matched_skills'])} ({skills})"
            why = r["lane_reason"]
            if len(why) > 45:
                why = why[:44] + "..."
            lines.append(f"{i:>2}  {r['score']:>5.1f}  {lane:<14} {r['company']:<18} "
                         f"{r['title']:<30} {matched:<60} {why}")
    else:
        lines.append("Queue is empty.")
    if result["gated"]:
        by_gate: dict[str, int] = {}
        for g in result["gated"]:
            by_gate[g["failed_gate"]] = by_gate.get(g["failed_gate"], 0) + 1
        lines += ["", "Gated out: " + ", ".join(f"{n} {gate}" for gate, n in sorted(by_gate.items()))]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rank job postings into a reviewable queue.")
    parser.add_argument("--data-dir", help="data directory (default: $JOBPIPE_DATA_DIR or repo data/)")
    parser.add_argument("--profile", help="profile JSON (default: $JOBPIPE_PROFILE or <data-dir>/profile.json)")
    parser.add_argument("--live-greenhouse", nargs="+", metavar="TOKEN",
                        help="LIVE: fetch these public Greenhouse boards over the network, "
                             "write <data-dir>/postings_live.csv, and rank that instead of "
                             "the synthetic demo postings")
    args = parser.parse_args(argv)

    data_dir = config.resolve_data_dir(args.data_dir)
    postings = config.postings_path(data_dir)
    if args.live_greenhouse:
        # Separate file: never overwrite the committed demo snapshot.
        postings = write_postings(GreenhouseLiveAdapter(args.live_greenhouse).run(),
                                  data_dir / "postings_live.csv")
    profile = config.profile_path(data_dir, args.profile)
    missing = [p for p in (postings, profile) if not Path(p).exists()]
    if missing:
        sys.exit("Missing input: " + ", ".join(str(p) for p in missing) + "\n"
                 "Point --data-dir at a folder with postings.csv and profile.json "
                 "(copy data/profile.example.json to start), or fetch real postings "
                 "with --live-greenhouse <board-token>.")
    print(format_queue(build_queue(postings, profile, config.ledger_path(data_dir))))


if __name__ == "__main__":
    main()
