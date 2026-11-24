"""parse_min_years / find_min_years on realistic posting phrasings.

find_min_years returns None when the text states no candidate requirement, so
"not found" is distinguishable from an explicit 0 ("0-2 years").
"""

import pytest

from pipeline.adapters.base import find_min_years, parse_min_years

CASES = [
    # (text, expected find_min_years)
    ("Requires 6+ years of Go. You will ship within 1 year.", 6),
    ("For over 20 years we have built payments software.", None),
    ("5+ years of experience required. Our company is 12 years old.", 5),
    ("at least three years of experience", 3),
    ("five (5)+ years of experience", 5),
    ("2 or more years of experience", 2),
    ("Years of experience: 4", 4),
    ("1.5 years of experience", 1),
    ("3—5 years of experience", 3),
    ("0-2 years of experience", 0),
    ("3+ years required, 5+ years preferred", 3),
    ("No experience needed.", None),
    # range spellings and forms from the review
    ("3–5 years of experience", 3),
    ("3 to 5 years of experience", 3),
    ("three to five years of experience", 3),
    ("2.5 years of experience", 2),
    # time windows are not requirements
    ("5+ years of experience. Within 1 year you will own a service.", 5),
    ("In the next 2 years you will grow. Requires 4 years of experience.", 4),
    ("Employees vest over the next 4 years. Minimum 3 years of experience.", 3),
    # company sentences are not requirements
    ("Founded 12 years ago. No other requirement.", None),
    ("We have been shipping since 2009, more than 10 years of growth.", None),
    # we/our/us/company only discard a sentence that states no requirement
    ("We require 5+ years of experience.", 5),
    ("Our team needs 4 years of experience with Go.", 4),
    ("You have 8 years of legal experience at a public company.", 8),
    ("Our company is 12 years old.", None),
    # no keyword sentence: smallest remaining wins
    ("2-4 years preferred, 5+ years ideal", 2),
    # a keyworded sentence beats an unkeyworded one
    ("Lead a team for 8 years. Requires 3 years of experience.", 3),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_find_min_years(text, expected):
    assert find_min_years(text) == expected


@pytest.mark.parametrize("text,expected", CASES)
def test_parse_min_years_is_find_or_zero(text, expected):
    assert parse_min_years(text) == (expected or 0)


@pytest.mark.parametrize("empty", ["", None])
def test_empty_input_is_unknown(empty):
    assert find_min_years(empty) is None
    assert parse_min_years(empty) == 0
