from collections import Counter
from pathlib import Path

import pytest

from pipeline.adapters.base import CANONICAL_KEYS, SourceAdapter, parse_min_years
from pipeline.adapters.company_careers import CompanyCareersAdapter
from pipeline.adapters.github_lists import GithubListsAdapter
from pipeline.adapters.ingest import ALL_ADAPTERS, build_postings, run_all_adapters
from pipeline.adapters.job_boards import JobBoardsAdapter
from pipeline.adapters.linkedin_alerts import LinkedInAlertsAdapter

from pipeline.ledger import fingerprint, load_resolved_fingerprints
from pipeline.scorer import load_postings

MASTER = Path(__file__).parent.parent / "data" / "postings.csv"
ADAPTERS = [LinkedInAlertsAdapter, JobBoardsAdapter, GithubListsAdapter, CompanyCareersAdapter]


def _by_title(rows, title):
    return next(r for r in rows if r["title"] == title)


@pytest.mark.parametrize("cls", ADAPTERS)
def test_fetch_raw_nonempty_and_output_is_canonical(cls):
    adapter = cls()
    assert isinstance(adapter, SourceAdapter)
    assert adapter.fetch_raw()
    rows = adapter.run()
    assert rows
    for row in rows:
        assert set(row) == set(CANONICAL_KEYS)
        for key in ("company", "title", "url", "description"):
            assert isinstance(row[key], str) and row[key]
        assert isinstance(row["min_years_experience"], int)
        assert row["min_years_experience"] >= 0


@pytest.mark.parametrize("cls,expected", [(LinkedInAlertsAdapter, 8), (JobBoardsAdapter, 8),
                                           (GithubListsAdapter, 7), (CompanyCareersAdapter, 7)])
def test_per_source_counts(cls, expected):
    assert len(cls().run()) == expected


def test_parse_min_years_takes_floor():
    assert parse_min_years("3+ years required, 5 years preferred") == 3
    assert parse_min_years("no experience stated") == 0


def test_parse_min_years_range_uses_floor():
    assert parse_min_years("0-2 years of experience") == 0
    assert parse_min_years("2-4 years preferred, 5+ years ideal") == 2
    assert parse_min_years("1 to 3 years") == 1


def test_linkedin_years_from_snippet_then_seniority():
    rows = LinkedInAlertsAdapter().run()
    assert _by_title(rows, "Machine Learning Engineer")["min_years_experience"] == 3  # snippet
    assert _by_title(rows, "Platform Engineer")["min_years_experience"] == 4  # seniority fallback
    assert _by_title(rows, "Software Engineer, New Grad")["min_years_experience"] == 0


def test_job_boards_metadata_then_text_fallback():
    rows = JobBoardsAdapter().run()
    assert _by_title(rows, "Backend Engineer I")["min_years_experience"] == 1  # metadata
    assert _by_title(rows, "Software Engineer, Infrastructure")["min_years_experience"] == 2  # text
    assert _by_title(rows, "ML Platform Engineer")["min_years_experience"] == 0  # malformed + no text


def test_github_lists_notes_and_sponsorship():
    rows = GithubListsAdapter().run()
    be = _by_title(rows, "Backend Engineer")
    assert be["min_years_experience"] == 3
    assert "Does Not Offer Sponsorship" in be["description"]


def test_company_careers_company_and_years():
    rows = CompanyCareersAdapter().run()
    assert {r["company"] for r in rows} == {"Northgate Robotics"}
    assert _by_title(rows, "Data Engineer, Telemetry")["min_years_experience"] == 3
    assert _by_title(rows, "Machine Learning Engineer")["min_years_experience"] == 0
    # "0-2 years" -> floor of the range
    assert _by_title(rows, "Software Engineer, Perception")["min_years_experience"] == 0


def test_master_postings_is_exactly_the_adapter_output():
    """data/postings.csv is a generated snapshot: it must equal the merged adapters."""
    master = load_postings(MASTER)
    merged = run_all_adapters()
    assert len(master) == len(merged)
    assert (Counter(fingerprint(r["company"], r["title"]) for r in master)
            == Counter(fingerprint(r["company"], r["title"]) for r in merged))
    assert [{**r, "min_years_experience": int(r["min_years_experience"])} for r in master] == merged


def test_build_postings_writes_canonical_deterministic_csv(tmp_path):
    out = tmp_path / "postings.csv"
    rows = build_postings(out_path=out)
    first = out.read_bytes()
    assert first.decode("utf-8").splitlines()[0] == ",".join(CANONICAL_KEYS)
    assert b"\r" not in first
    assert rows == run_all_adapters()
    build_postings(out_path=out)
    assert out.read_bytes() == first


def test_demo_data_has_crosssource_repost_and_ledger_hits():
    by_fp = {}
    for cls in ALL_ADAPTERS:
        for r in cls().run():
            by_fp.setdefault(fingerprint(r["company"], r["title"]), set()).add(cls.source_name)
    assert any(len(srcs) > 1 for srcs in by_fp.values())
    assert len(load_resolved_fingerprints(MASTER.parent / "resolved_roles.csv") & set(by_fp)) >= 1


def test_run_all_adapters_sums_sources():
    expected = sum(len(cls().run()) for cls in ALL_ADAPTERS)
    assert len(run_all_adapters()) == expected
    assert expected > 0
