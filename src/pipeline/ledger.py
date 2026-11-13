"""Resolved-roles ledger.

A CSV-backed record of roles that have already been reviewed and resolved, so
the same role is not surfaced again when it is reposted under a new URL.
Identity is a normalized "company|title" fingerprint rather than a URL.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LEDGER_PATH = Path("data/resolved_roles.csv")

RESOLVED_FIELDS = ["fingerprint", "company", "title", "status", "resolved_date", "url"]

# Exact match after normalization only, never fuzzy: fuzzy matching risks
# collapsing two distinct roles at one company that have similar titles.
_NOISE_RE = re.compile(r"\b(20\d{2}|new college grad|new grad|college grad|undergrads?)\b")
_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def clean(s: str | None) -> str:
    """Replace unicode dashes / replacement chars with '-' and strip."""
    s = s or ""
    return (s.replace("–", "-").replace("—", "-")
             .replace("‑", "-").replace("�", "-")).strip()


def normalize_fingerprint_part(s: str | None) -> str:
    """Lowercase, drop year/cohort noise words and punctuation, collapse spaces."""
    s = (s or "").lower()
    s = _NOISE_RE.sub(" ", s)
    s = _PUNCT_RE.sub(" ", s)
    return " ".join(s.split())


def fingerprint(company: str, title: str) -> str:
    """Normalized 'company|title' identity shared by every URL of the same role."""
    return f"{normalize_fingerprint_part(company)}|{normalize_fingerprint_part(title)}"


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolved_status_for(fp: str, path: Path = DEFAULT_LEDGER_PATH) -> str | None:
    """Current ledger status for a fingerprint, or None if it has no row."""
    for r in _read_rows(Path(path)):
        if (r.get("fingerprint") or "").strip() == fp:
            return (r.get("status") or "").strip() or None
    return None


def load_resolved_fingerprints(path: Path = DEFAULT_LEDGER_PATH) -> set[str]:
    """Fingerprints of every resolved role. A missing file yields an empty set;
    rows lacking a fingerprint are skipped with a note on stderr."""
    path = Path(path)
    out: set[str] = set()
    for r in _read_rows(path):
        fp = (r.get("fingerprint") or "").strip()
        if not fp:
            print(f"[ledger] skipping malformed row (no fingerprint) in {path.name}",
                  file=sys.stderr)
            continue
        out.add(fp)
    return out


def upsert_resolved_role(fp: str, company: str, title: str, status: str, url: str,
                         path: Path = DEFAULT_LEDGER_PATH) -> None:
    """Add a fingerprint's row, or refresh the existing one in place.

    Exactly one row exists per fingerprint: re-resolving a role overwrites its
    company/title/status/date/url instead of appending a duplicate.
    """
    path = Path(path)
    rows = _read_rows(path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = {"fingerprint": fp, "company": company, "title": title,
             "status": status, "resolved_date": today, "url": url}
    for r in rows:
        if (r.get("fingerprint") or "").strip() == fp:
            r.update(entry)
            break
    else:
        rows.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RESOLVED_FIELDS)
        w.writeheader()
        w.writerows(rows)
