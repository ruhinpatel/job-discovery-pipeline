"""Candidate-queue tests.

Unit tests run against small FROZEN fixtures in tests/fixtures/ so their
assertions do not move when the demo data in data/ grows. One smoke test reads
the real demo files and checks only invariants (no hard-coded counts).
"""

import shutil
from pathlib import Path

import pytest

from pipeline.ledger import fingerprint, upsert_resolved_role
from pipeline.candidate_queue import build_queue, format_queue

FIXTURES = Path(__file__).parent / "fixtures"
POSTINGS = FIXTURES / "postings.csv"
REPOSTS = FIXTURES / "postings_with_reposts.csv"
PROFILE = FIXTURES / "profile.json"
DATA = Path(__file__).parent.parent / "data"


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    dest = tmp_path / "resolved_roles.csv"
    shutil.copy(FIXTURES / "resolved_roles.csv", dest)
    return dest


def test_ledger_suppresses_resolved_roles(ledger: Path):
    result = build_queue(POSTINGS, PROFILE, ledger)
    assert [r["company"] for r in result["queue"]] == ["Initech Systems"]
    assert all(r["status"] == "kept" for r in result["queue"])
    assert all(r["status"] == "suppressed" for r in result["suppressed"])


def test_suppressed_count_includes_reposted_duplicate(ledger: Path):
    result = build_queue(POSTINGS, PROFILE, ledger)
    assert result["total"] == 5
    assert result["suppressed_count"] == 4  # both Acme URLs share one fingerprint
    assert len(result["suppressed"]) == 4
    assert result["duplicate_count"] == 0
    assert (result["suppressed_count"] + result["duplicate_count"]
            + len(result["queue"])) == result["total"]


def test_queue_sorted_descending_by_score(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    scores = [r["score"] for r in result["queue"]]
    # Acme's two reposts collapse to one row in-batch, so 4 distinct roles remain.
    assert len(scores) == 4
    assert scores == sorted(scores, reverse=True)


def test_missing_ledger_suppresses_nothing(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    assert result["suppressed_count"] == 0
    assert result["total"] == 5
    assert len(result["queue"]) + result["duplicate_count"] == 5


def test_empty_ledger_suppresses_nothing(tmp_path: Path):
    empty = tmp_path / "empty.csv"
    empty.write_text("fingerprint,company,title,status,resolved_date,url\n", encoding="utf-8")
    assert build_queue(POSTINGS, PROFILE, empty)["suppressed_count"] == 0


def test_resolving_a_role_removes_it_from_queue(ledger: Path):
    fp = fingerprint("Initech Systems", "Backend Engineer")
    upsert_resolved_role(fp, "Initech Systems", "Backend Engineer", "reviewed",
                         "https://jobs.example.test/initech/be-3", ledger)
    result = build_queue(POSTINGS, PROFILE, ledger)
    assert result["queue"] == []
    assert result["suppressed_count"] == 5
    assert "Queue is empty" in format_queue(result)


def test_unresolved_repost_pair_collapses_to_best_scoring_row(tmp_path: Path):
    result = build_queue(REPOSTS, PROFILE, tmp_path / "missing.csv")
    initech = [r for r in result["queue"] if r["company"] == "Initech Systems"]
    assert len(initech) == 1
    assert initech[0]["url"] == "https://jobs.example.test/initech/be-3"  # higher score kept
    assert [d["url"] for d in result["duplicates"]] == ["https://mirror.example.test/view/5551"]
    assert result["duplicates"][0]["status"] == "duplicate"
    assert result["duplicates"][0]["fingerprint"] == initech[0]["fingerprint"]


def test_duplicate_tie_keeps_first_in_input_order(tmp_path: Path):
    csv_path = tmp_path / "ties.csv"
    csv_path.write_text(
        "company,title,url,description,min_years_experience\n"
        "Tie Co,Software Engineer,https://a.example.test/1,Python,0\n"
        "Tie Co,Software Engineer,https://b.example.test/2,Python,0\n", encoding="utf-8")
    result = build_queue(csv_path, PROFILE, tmp_path / "missing.csv")
    assert [r["url"] for r in result["queue"]] == ["https://a.example.test/1"]
    assert [d["url"] for d in result["duplicates"]] == ["https://b.example.test/2"]


def test_counts_reconcile_with_reposts_and_ledger(ledger: Path):
    result = build_queue(REPOSTS, PROFILE, ledger)
    assert result["duplicate_count"] == len(result["duplicates"]) == 1
    assert (result["suppressed_count"] + result["duplicate_count"]
            + len(result["queue"])) == result["total"]
    header = format_queue(result).splitlines()[0]
    assert "1 in-batch duplicates" in header


def test_demo_data_smoke_invariants():
    """Reads the real data/ demo files; asserts invariants only, no counts."""
    result = build_queue(DATA / "postings.csv", DATA / "profile.json",
                         DATA / "resolved_roles.csv")
    assert result["total"] > 0
    assert result["queue"]
    scores = [r["score"] for r in result["queue"]]
    assert scores == sorted(scores, reverse=True)
    assert (result["suppressed_count"] + result["duplicate_count"]
            + len(result["queue"])) == result["total"]
    fps = [r["fingerprint"] for r in result["queue"]]
    assert len(fps) == len(set(fps))
