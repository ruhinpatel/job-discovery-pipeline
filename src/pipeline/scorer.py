"""Fit-scoring rubric.

Scores a posting against a candidate profile using deterministic keyword/skill
overlap. This stands in for the real system's LLM-based scoring call so the
public demo makes no API calls and uses no real candidate data; the rubric
structure (weighted categories, 0-100 output) is the part worth keeping.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("data/profile.json")
DEFAULT_POSTINGS_PATH = Path("data/postings.csv")

# Weights sum to 1.0. skills_overlap carries the most weight because it is the
# rubric's main signal; role_title_match and seniority_fit are coarse gates.
RUBRIC_WEIGHTS = {
    "skills_overlap": 0.60,
    "role_title_match": 0.25,
    "seniority_fit": 0.15,
}

_WORD_RE = re.compile(r"[a-z0-9+]+")


def load_profile(path: Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_postings(path: Path = DEFAULT_POSTINGS_PATH) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Skills whose lowercase form is also an ordinary English word. Matching them
# case-insensitively makes "ready to go / go live" score a full Go match, so
# these match only on case-sensitive aliases in the original description.
# Deliberately a small special-case table, not general disambiguation.
_AMBIGUOUS_SKILLS = {"go": ["Go", "Golang"]}


def _skills_overlap(description: str, skills: list[str]) -> tuple[float, list[str]]:
    """Fraction of the profile's skills that appear as whole words in the
    description (case-insensitive). Skills containing a space, "+" or "/" (e.g. "CI/CD", which the word
    tokenizer would split apart) match as substrings. Skills listed in
    _AMBIGUOUS_SKILLS match only via case-sensitive aliases (see above)."""
    text = description.lower()
    words = set(_WORD_RE.findall(text))
    original_words = set(re.findall(r"[A-Za-z0-9+]+", description))
    matched = []
    for skill in skills:
        skill_l = skill.lower()
        if skill_l in _AMBIGUOUS_SKILLS:
            hit = any(alias in original_words for alias in _AMBIGUOUS_SKILLS[skill_l])
        elif " " in skill_l or "+" in skill_l or "/" in skill_l:
            hit = skill_l in text
        else:
            hit = skill_l in words
        if hit:
            matched.append(skill)
    ratio = len(matched) / len(skills) if skills else 0.0
    return min(ratio, 1.0), matched


def _role_title_match(title: str, role_preferences: list[str]) -> bool:
    title_l = title.lower()
    return any(pref.lower() in title_l for pref in role_preferences)


def _seniority_fit(min_years_posting: int, min_years_profile: int, max_years_profile: int) -> float:
    """1.0 if the posting's stated floor sits inside the profile's range, 0.0
    if it is above the profile's ceiling (profile is under-qualified)."""
    if min_years_posting > max_years_profile:
        return 0.0
    if min_years_posting < min_years_profile:
        return 0.0
    return 1.0


def score_posting(posting: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Score one posting against the profile. Returns the 0-100 score plus
    the per-category breakdown, so a reviewer can see why a row ranked where
    it did instead of trusting an opaque number."""
    skills_overlap, matched_skills = _skills_overlap(
        posting.get("description", ""), profile["skills"])
    role_match = _role_title_match(posting.get("title", ""), profile["role_preferences"])
    seniority_fit = _seniority_fit(
        int(posting.get("min_years_experience", 0) or 0),
        profile["min_years_experience"],
        profile["max_years_experience"],
    )

    breakdown = {
        "skills_overlap": skills_overlap,
        "role_title_match": 1.0 if role_match else 0.0,
        "seniority_fit": seniority_fit,
    }
    score = sum(breakdown[k] * w for k, w in RUBRIC_WEIGHTS.items()) * 100

    return {
        "company": posting.get("company", ""),
        "title": posting.get("title", ""),
        "url": posting.get("url", ""),
        "score": round(score, 1),
        "breakdown": breakdown,
        "matched_skills": matched_skills,
    }


def score_all(postings: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted((score_posting(p, profile) for p in postings),
                  key=lambda r: r["score"], reverse=True)
