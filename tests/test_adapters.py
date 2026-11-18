import pytest

from pipeline.adapters.base import CANONICAL_KEYS, SourceAdapter, parse_min_years
from pipeline.adapters.company_careers import CompanyCareersAdapter
from pipeline.adapters.github_lists import GithubListsAdapter
from pipeline.adapters.ingest import ALL_ADAPTERS, run_all_adapters
from pipeline.adapters.job_boards import JobBoardsAdapter
from pipeline.adapters.linkedin_alerts import LinkedInAlertsAdapter

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


def test_run_all_adapters_sums_sources():
    expected = sum(len(cls().run()) for cls in ALL_ADAPTERS)
    assert len(run_all_adapters()) == expected
    assert expected > 0
