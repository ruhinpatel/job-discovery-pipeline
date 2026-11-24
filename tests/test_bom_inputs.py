"""Files saved by Excel ("CSV UTF-8") or older Notepad start with a UTF-8 BOM.
A BOM must not corrupt the first column header or break JSON parsing."""

from pathlib import Path

from pipeline.ledger import load_resolved_fingerprints
from pipeline.scorer import load_postings, load_profile


def _write_bom(path: Path, text: str) -> Path:
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    return path


def test_postings_csv_with_bom_keeps_first_column_name(tmp_path: Path):
    path = _write_bom(tmp_path / "postings.csv",
                      "company,title,url,description,min_years_experience\n"
                      "Alpha,Software Engineer,https://a.test/1,Python,0\n")
    rows = load_postings(path)
    assert rows[0]["company"] == "Alpha"


def test_profile_json_with_bom_loads(tmp_path: Path):
    path = _write_bom(tmp_path / "profile.json", '{"skills": ["Python"]}')
    assert load_profile(path) == {"skills": ["Python"]}


def test_ledger_csv_with_bom_still_suppresses(tmp_path: Path):
    path = _write_bom(tmp_path / "resolved_roles.csv",
                      "fingerprint,company,title,status,resolved_date,url\n"
                      "alpha|software engineer,Alpha,Software Engineer,reviewed,2026-01-01,u\n")
    assert load_resolved_fingerprints(path) == {"alpha|software engineer"}
