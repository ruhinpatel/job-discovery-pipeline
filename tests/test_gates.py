from pipeline.gates import GateResult, check_gates

PROFILE = {
    "max_years_experience": 2,
    "needs_sponsorship": True,
    "can_obtain_clearance": False,
    "allowed_locations": ["Remote - US", "New York, NY"],
}


def _posting(**overrides):
    base = {"min_years_experience": 1, "location": "Remote - US",
            "sponsorship_offered": True, "requires_clearance": False}
    return {**base, **overrides}


def test_eligible_posting_passes():
    assert check_gates(_posting(), PROFILE) == GateResult(True, None, None)


def test_min_yoe_boundary():
    assert check_gates(_posting(min_years_experience=2), PROFILE).passed
    result = check_gates(_posting(min_years_experience=3), PROFILE)
    assert not result.passed and result.failed_gate == "min_yoe"
    assert "3y" in result.reason and "2y" in result.reason


def test_work_authorization():
    result = check_gates(_posting(sponsorship_offered=False), PROFILE)
    assert result.failed_gate == "work_authorization" and result.reason == "no sponsorship offered"
    # A candidate who needs no sponsorship is not gated by its absence.
    assert check_gates(_posting(sponsorship_offered=False),
                       {**PROFILE, "needs_sponsorship": False}).passed


def test_clearance():
    result = check_gates(_posting(requires_clearance=True), PROFILE)
    assert result.failed_gate == "clearance" and result.reason == "clearance required"
    assert check_gates(_posting(requires_clearance=True),
                       {**PROFILE, "can_obtain_clearance": True}).passed


def test_location():
    assert check_gates(_posting(location="New York, NY"), PROFILE).passed
    result = check_gates(_posting(location="London, UK"), PROFILE)
    assert result.failed_gate == "location" and "London, UK" in result.reason


def test_first_failure_wins_in_documented_order():
    everything_wrong = _posting(min_years_experience=9, sponsorship_offered=False,
                                requires_clearance=True, location="London, UK")
    assert check_gates(everything_wrong, PROFILE).failed_gate == "min_yoe"
    no_yoe = {**everything_wrong, "min_years_experience": 0}
    assert check_gates(no_yoe, PROFILE).failed_gate == "work_authorization"
    no_auth = {**no_yoe, "sponsorship_offered": True}
    assert check_gates(no_auth, PROFILE).failed_gate == "clearance"
    no_clear = {**no_auth, "requires_clearance": False}
    assert check_gates(no_clear, PROFILE).failed_gate == "location"


def test_missing_posting_fields_never_disqualify():
    assert check_gates({"min_years_experience": 0}, PROFILE).passed
    assert check_gates({}, PROFILE).passed


def test_missing_profile_fields_never_disqualify():
    bare_profile = {"max_years_experience": 2}
    posting = _posting(sponsorship_offered=False, requires_clearance=True, location="Mars")
    assert check_gates(posting, bare_profile).passed


def test_csv_string_booleans_are_understood():
    assert check_gates(_posting(sponsorship_offered="False"), PROFILE).failed_gate == "work_authorization"
    assert check_gates(_posting(requires_clearance="True"), PROFILE).failed_gate == "clearance"
    assert check_gates(_posting(sponsorship_offered="", requires_clearance=""), PROFILE).passed


def test_multi_location_passes_if_any_part_allowed():
    # Real Greenhouse shapes: "|" and ";" separators, "New York City" spelling.
    assert check_gates(_posting(location="London, UK | New York City, NY"), PROFILE).passed
    assert check_gates(_posting(location="London, UK; Remote - US; Tokyo, Japan"), PROFILE).passed
    assert check_gates(_posting(location="new york,  ny"), PROFILE).passed  # case/space


def test_multi_location_fails_when_no_part_allowed():
    result = check_gates(_posting(location="London, UK | Tokyo, Japan; Zürich, CH"), PROFILE)
    assert result.failed_gate == "location"


def test_blank_separator_parts_do_not_match_or_crash():
    assert check_gates(_posting(location=" | ; "), PROFILE).failed_gate == "location"


def test_empty_allowed_locations_means_no_restriction():
    profile = {**PROFILE, "allowed_locations": []}
    assert check_gates(_posting(location="London, UK"), profile).passed


def test_trailing_hybrid_us_and_usa_are_ignored_when_matching():
    assert check_gates(_posting(location="New York, NY (Hybrid)"), PROFILE).passed
    assert check_gates(_posting(location="New York, NY (US)"), PROFILE).passed
    assert check_gates(_posting(location="New York, NY, USA"), PROFILE).passed
    assert check_gates(_posting(location="London, UK | New York, NY, USA"), PROFILE).passed


def test_location_suffix_stripping_does_not_make_other_places_eligible():
    assert check_gates(_posting(location="London, UK (Hybrid)"), PROFILE).failed_gate == "location"
    assert check_gates(_posting(location="Boston, MA, USA"), PROFILE).failed_gate == "location"
