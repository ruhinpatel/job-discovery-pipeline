"""Ingest: run every adapter and merge into one canonical posting list.

This is the merge step that feeds the existing dedup -> score -> rank flow
(candidate_queue). Because each adapter already emits the canonical schema,
concatenation is all that is needed here; duplicate postings across sources
(same role, different URL) are the ledger's job downstream, not this layer's.
Output is a candidate list for human review.

`data/postings.csv` (the master set the queue scores) is a GENERATED snapshot
of this merged adapter output, written by `build_postings()` /
`python src/pipeline/adapters/ingest.py --write`. It is not hand-maintained:
edit the raw fixtures in `data/raw/` and regenerate, so the adapters are the
single origin of the demo data and every downstream count reconciles to them.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/adapters/ on sys.path, not src/.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline import config
from pipeline.adapters.base import CANONICAL_KEYS, SourceAdapter
from pipeline.adapters.company_careers import CompanyCareersAdapter
from pipeline.adapters.github_lists import GithubListsAdapter
from pipeline.adapters.job_boards import JobBoardsAdapter
from pipeline.adapters.linkedin_alerts import LinkedInAlertsAdapter

ALL_ADAPTERS: tuple[type[SourceAdapter], ...] = (
    LinkedInAlertsAdapter,
    JobBoardsAdapter,
    GithubListsAdapter,
    CompanyCareersAdapter,
)


def run_all_adapters(raw_dir: Path | None = None) -> list[dict]:
    """Run each adapter and return all normalized postings, source order kept."""
    postings: list[dict] = []
    for cls in ALL_ADAPTERS:
        postings.extend(cls(raw_dir).run())
    return postings


DEFAULT_POSTINGS_PATH = config.postings_path(config.DEFAULT_DATA_DIR)


def build_postings(raw_dir: Path | None = None, out_path: Path | None = None) -> list[dict]:
    """Write the merged adapter output as the master `postings.csv` and return it.

    Row order is deterministic: adapter order from ALL_ADAPTERS, each adapter's
    own record order preserved. Line endings are fixed to LF so regenerating on
    any OS yields a byte-identical file. Deduplication is deliberately NOT done
    here: the master keeps reposts so the queue's ledger/dedup step has real
    work to show.
    """
    postings = run_all_adapters(raw_dir)
    write_postings(postings, out_path)
    return postings


def write_postings(postings: list[dict], out_path: Path | None = None) -> Path:
    """Write canonical postings to a CSV (LF endings, canonical column order)."""
    out_path = Path(out_path) if out_path else DEFAULT_POSTINGS_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_KEYS, lineterminator="\n")
        w.writeheader()
        w.writerows(postings)
    return out_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic-fixture adapters.")
    parser.add_argument("--data-dir", help="data directory (default: $JOBPIPE_DATA_DIR or repo data/)")
    parser.add_argument("--write", action="store_true", help="regenerate <data-dir>/postings.csv")
    args = parser.parse_args(argv)
    data_dir = config.resolve_data_dir(args.data_dir)
    raw = config.raw_dir(data_dir)
    total = 0
    for cls in ALL_ADAPTERS:
        adapter = cls(raw)
        n = len(adapter.run())
        total += n
        print(f"{adapter.source_name}: {n}")
    print(f"total: {total}")
    if args.write:
        out = config.postings_path(data_dir)
        build_postings(raw, out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
