import shutil
from pathlib import Path

import pytest

from pipeline.ledger import fingerprint, upsert_resolved_role
from pipeline.candidate_queue import build_queue, format_queue

DATA = Path(__file__).parent.parent / "data"
POSTINGS = DATA / "postings.csv"
PROFILE = DATA / "profile.json"


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    dest = tmp_path / "resolved_roles.csv"
    shutil.copy(DATA / "resolved_roles.csv", dest)
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
    assert result["suppressed_count"] + len(result["queue"]) == result["total"]


def test_queue_sorted_descending_by_score(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    scores = [r["score"] for r in result["queue"]]
    assert len(scores) == 5
    assert scores == sorted(scores, reverse=True)


def test_missing_ledger_suppresses_nothing(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    assert result["suppressed_count"] == 0
    assert len(result["queue"]) == result["total"] == 5


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
