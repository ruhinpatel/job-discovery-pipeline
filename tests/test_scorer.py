from pathlib import Path

from pipeline.scorer import load_postings, load_profile, score_all, score_posting

PROFILE = Path(__file__).parent.parent / "data" / "profile.json"
POSTINGS = Path(__file__).parent.parent / "data" / "postings.csv"


def test_load_profile_has_expected_shape():
    profile = load_profile(PROFILE)
    assert profile["skills"]
    assert profile["role_preferences"]
    assert profile["min_years_experience"] <= profile["max_years_experience"]


def test_strong_match_scores_high():
    profile = load_profile(PROFILE)
    posting = {
        "company": "Acme", "title": "Backend Engineer",
        "description": "Build in Go and Python, deployed on AWS and Kubernetes with CI/CD.",
        "min_years_experience": "1",
    }
    result = score_posting(posting, profile)
    assert result["score"] > 60
    assert "Go" in result["matched_skills"]


def test_over_qualification_floor_zeroes_seniority_fit():
    profile = load_profile(PROFILE)
    posting = {
        "company": "Acme", "title": "Backend Engineer",
        "description": "Python, Go, AWS.", "min_years_experience": "5",
    }
    result = score_posting(posting, profile)
    assert result["breakdown"]["seniority_fit"] == 0.0


def test_no_skill_overlap_scores_near_zero():
    profile = load_profile(PROFILE)
    posting = {
        "company": "Acme", "title": "Marketing Analyst",
        "description": "Excel, Salesforce, campaign copywriting.", "min_years_experience": "0",
    }
    result = score_posting(posting, profile)
    assert result["score"] < 20


def test_score_is_bounded_0_to_100():
    profile = load_profile(PROFILE)
    for posting in load_postings(POSTINGS):
        result = score_posting(posting, profile)
        assert 0.0 <= result["score"] <= 100.0


def test_score_all_sorts_descending():
    profile = load_profile(PROFILE)
    postings = load_postings(POSTINGS)
    ranked = score_all(postings, profile)
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert len(ranked) == len(postings)


def test_ci_cd_skill_matches_despite_slash():
    profile = load_profile(PROFILE)
    posting = {"company": "X", "title": "Engineer",
               "description": "You will own our CI/CD pipeline.", "min_years_experience": "0"}
    assert "CI/CD" in score_posting(posting, profile)["matched_skills"]
