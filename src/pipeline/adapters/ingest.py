"""Ingest: run every adapter and merge into one canonical posting list.

This is the merge step that feeds the existing dedup -> score -> rank flow
(candidate_queue). Because each adapter already emits the canonical schema,
concatenation is all that is needed here; duplicate postings across sources
(same role, different URL) are the ledger's job downstream, not this layer's.
Output is a candidate list for human review.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__":
    # Direct script run puts src/pipeline/adapters/ on sys.path, not src/.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.adapters.base import SourceAdapter
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


def main() -> None:
    total = 0
    for cls in ALL_ADAPTERS:
        adapter = cls()
        n = len(adapter.run())
        total += n
        print(f"{adapter.source_name}: {n}")
    print(f"total: {total}")


if __name__ == "__main__":
    main()
