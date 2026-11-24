import csv
import shutil
from pathlib import Path

import pytest

from pipeline.ledger import (
    fingerprint,
    load_resolved_fingerprints,
    normalize_fingerprint_part,
    resolved_status_for,
    upsert_resolved_role,
)

# Frozen 3-row fixture: independent of the growing demo data in data/.
FIXTURE = Path(__file__).parent / "fixtures" / "resolved_roles.csv"


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    dest = tmp_path / "resolved_roles.csv"
    shutil.copy(FIXTURE, dest)
    return dest


def test_normalization_strips_noise_and_punctuation():
    assert normalize_fingerprint_part("Software Engineer, New Grad 2027!") == "software engineer"


def test_same_role_different_urls_same_fingerprint():
    a = fingerprint("Acme Robotics", "Software Engineer New Grad 2027")
    b = fingerprint("ACME  Robotics", "Software Engineer - New Grad")
    assert a == b == "acme robotics|software engineer"


def test_distinct_roles_stay_distinct():
    assert fingerprint("Acme Robotics", "Software Engineer") != fingerprint(
        "Acme Robotics", "Software Engineer II")


def test_load_fixture(ledger: Path):
    fps = load_resolved_fingerprints(ledger)
    assert len(fps) == 3
    assert "northwind data|data engineer" in fps


def test_load_missing_file_is_empty(tmp_path: Path):
    assert load_resolved_fingerprints(tmp_path / "nope.csv") == set()


def test_status_lookup(ledger: Path):
    assert resolved_status_for("northwind data|data engineer", ledger) == "skipped"
    assert resolved_status_for("initech systems|backend engineer", ledger) is None


def test_upsert_adds_new_fingerprint(ledger: Path):
    fp = fingerprint("Initech Systems", "Backend Engineer")
    upsert_resolved_role(fp, "Initech Systems", "Backend Engineer", "reviewed",
                         "https://jobs.example.test/initech/be-3", ledger)
    assert fp in load_resolved_fingerprints(ledger)
    assert resolved_status_for(fp, ledger) == "reviewed"
    assert len(list(csv.DictReader(open(ledger, encoding="utf-8")))) == 4


def test_upsert_refreshes_without_duplicate(ledger: Path):
    fp = "northwind data|data engineer"
    upsert_resolved_role(fp, "Northwind Data", "Data Engineer", "reviewed",
                         "https://mirror.example.test/view/999", ledger)
    rows = list(csv.DictReader(open(ledger, encoding="utf-8")))
    matches = [r for r in rows if r["fingerprint"] == fp]
    assert len(rows) == 3 and len(matches) == 1
    assert matches[0]["status"] == "reviewed"
    assert matches[0]["url"].endswith("/999")


def test_upsert_creates_file_and_parent(tmp_path: Path):
    p = tmp_path / "sub" / "ledger.csv"
    upsert_resolved_role("a|b", "A", "B", "reviewed", "https://x.example.test/1", p)
    assert load_resolved_fingerprints(p) == {"a|b"}


def test_c_plus_plus_and_c_sharp_stay_distinct_from_each_other_and_from_c():
    fps = {fingerprint("Acme", t) for t in ("C++ Engineer", "C# Engineer", "C Engineer")}
    assert len(fps) == 3


def test_c_plus_plus_and_c_sharp_inside_longer_titles():
    assert normalize_fingerprint_part("Senior C++/Python Developer") == "senior cplusplus python developer"
    assert normalize_fingerprint_part("C#/.NET Engineer") == "csharp net engineer"
    assert normalize_fingerprint_part("Abc++ Engineer") == "abc engineer"  # not a C++ token
