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
    assert result["gated_count"] == 0
    assert (result["suppressed_count"] + result["gated_count"] + result["duplicate_count"]
            + len(result["queue"])) == result["total"]


def test_queue_sorted_descending_by_score(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    scores = [r["score"] for r in result["queue"]]
    # Acme's two reposts collapse in-batch and Northwind (3y floor) is gated: 3 remain.
    assert len(scores) == 3
    assert scores == sorted(scores, reverse=True)


def test_missing_ledger_suppresses_nothing(tmp_path: Path):
    result = build_queue(POSTINGS, PROFILE, tmp_path / "missing.csv")
    assert result["suppressed_count"] == 0
    assert result["total"] == 5
    assert len(result["queue"]) + result["duplicate_count"] + result["gated_count"] == 5


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
    assert (result["suppressed_count"] + result["gated_count"] + result["duplicate_count"]
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
    assert (result["suppressed_count"] + result["gated_count"] + result["duplicate_count"]
            + len(result["queue"])) == result["total"]
    assert all("lane" in r for r in result["queue"])
    fps = [r["fingerprint"] for r in result["queue"]]
    assert len(fps) == len(set(fps))


def _write_postings(tmp_path: Path, rows: list[str]) -> Path:
    csv_path = tmp_path / "postings.csv"
    csv_path.write_text(
        "company,title,url,description,min_years_experience,location,"
        "sponsorship_offered,requires_clearance,referral\n" + "\n".join(rows) + "\n",
        encoding="utf-8")
    return csv_path


def _decision_profile(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    path.write_text(
        '{"role_preferences": ["Software Engineer"], "skills": ["Python"], '
        '"min_years_experience": 0, "max_years_experience": 2, '
        '"allowed_locations": ["Remote - US"], "needs_sponsorship": true, '
        '"can_obtain_clearance": false}', encoding="utf-8")
    return path


def test_gated_rows_excluded_from_queue_and_dedup(tmp_path: Path):
    # Same role twice: the higher-scoring repost fails the location gate, so
    # it must not win dedup and displace the eligible row.
    postings = _write_postings(tmp_path, [
        "Dup Co,Software Engineer,https://a.example.test/1,Python,0,Remote - US,True,False,False",
        "Dup Co,Software Engineer,https://b.example.test/2,Python Python,0,London UK,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert [r["url"] for r in result["queue"]] == ["https://a.example.test/1"]
    assert result["duplicate_count"] == 0
    assert result["gated_count"] == len(result["gated"]) == 1
    gated = result["gated"][0]
    assert gated["status"] == "gated" and gated["failed_gate"] == "location"
    assert gated["reason"]


def test_each_gate_routes_to_gated_bucket(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "A,Software Engineer,https://x.example.test/1,Python,5,Remote - US,True,False,False",
        "B,Software Engineer,https://x.example.test/2,Python,0,Remote - US,False,False,False",
        "C,Software Engineer,https://x.example.test/3,Python,0,Remote - US,True,True,False",
        "D,Software Engineer,https://x.example.test/4,Python,0,Remote - US,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert [g["failed_gate"] for g in result["gated"]] == [
        "min_yoe", "work_authorization", "clearance"]
    assert [r["company"] for r in result["queue"]] == ["D"]


def test_lane_zero_survivors_stay_in_queue_flagged(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "Weak Co,Facilities Technician,https://w.example.test/1,No skills here,0,Remote - US,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert len(result["queue"]) == 1
    row = result["queue"][0]
    assert row["lane"] == 0 and row["lane_name"] == "SKIP" and row["lane_reason"]


def test_referral_lifts_low_score_row_to_lane_one(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "Warm Co,Facilities Technician,https://w.example.test/1,No skills here,0,Remote - US,True,False,True",
    ])
    row = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")["queue"][0]
    assert row["lane"] == 1


def test_format_queue_shows_lane_column_and_gated_summary(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "A,Software Engineer,https://x.example.test/1,Python,5,Remote - US,True,False,False",
        "D,Software Engineer,https://x.example.test/4,Python,0,Remote - US,True,False,False",
    ])
    text = format_queue(build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv"))
    assert "Lane" in text and "1 gated" in text and "Gated out: 1 min_yoe" in text


def test_empty_urls_do_not_share_gate_data(tmp_path: Path):
    # Three rows with no URL: each must be gated on its OWN data, not on
    # whichever row happens to be last.
    postings = _write_postings(tmp_path, [
        "Ok Co,Software Engineer,,Python,0,Remote - US,True,False,False",
        "Senior Co,Software Engineer,,Python,9,Remote - US,True,False,False",
        "Fine Co,Software Engineer,,Python,0,Remote - US,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert sorted(r["company"] for r in result["queue"]) == ["Fine Co", "Ok Co"]
    assert [g["company"] for g in result["gated"]] == ["Senior Co"]
    assert result["gated"][0]["failed_gate"] == "min_yoe"


def test_duplicate_urls_do_not_share_gate_data(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "Ok Co,Software Engineer,https://same.example.test/1,Python,0,Remote - US,True,False,False",
        "Far Co,Backend Engineer,https://same.example.test/1,Python,0,London UK,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert [r["company"] for r in result["queue"]] == ["Ok Co"]
    assert [g["company"] for g in result["gated"]] == ["Far Co"]
    assert result["gated"][0]["failed_gate"] == "location"


def test_queue_rows_carry_their_own_stated_years(tmp_path: Path):
    postings = _write_postings(tmp_path, [
        "A Co,Software Engineer,https://same.example.test/1,Python,1,Remote - US,True,False,False",
        "B Co,Platform Engineer,https://same.example.test/1,Python,2,Remote - US,True,False,False",
    ])
    result = build_queue(postings, _decision_profile(tmp_path), tmp_path / "missing.csv")
    assert {r["company"]: r["min_years_experience"] for r in result["queue"]} == {"A Co": 1, "B Co": 2}
