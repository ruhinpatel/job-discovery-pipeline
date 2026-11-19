import pytest

from pipeline import lanes
from pipeline.gates import GateResult
from pipeline.lanes import assign_lane
from pipeline.router import TASK_TIERS, route

PASSED = GateResult(passed=True)
FAILED = GateResult(passed=False, failed_gate="location", reason="location not allowed")


@pytest.mark.parametrize("score,lane", [(0, 0), (59, 0), (59.9, 0), (60, 2), (69, 2),
                                        (69.9, 2), (70, 1), (100, 1)])
def test_score_boundaries_without_referral(score, lane):
    assert assign_lane(PASSED, score, referral=False).lane == lane


def test_referral_forces_lane_one_at_low_score():
    d = assign_lane(PASSED, 5, referral=True)
    assert d.lane == 1 and d.name == "FAST-APPLY" and d.model_task == "score"


def test_gate_failure_forces_lane_zero_even_with_referral_and_high_score():
    d = assign_lane(FAILED, 99, referral=True)
    assert d.lane == 0 and d.name == "SKIP" and d.model_task is None
    assert "location" in d.reason


def test_fresh_posting_lifts_moderate_fit_only():
    assert assign_lane(PASSED, 65, referral=False, is_fresh=True).lane == 1
    assert assign_lane(PASSED, 60, referral=False, is_fresh=True).lane == 1
    assert assign_lane(PASSED, 59, referral=False, is_fresh=True).lane == 0  # fit floor holds
    assert assign_lane(PASSED, 65, referral=False).lane == 2  # is_fresh defaults False


def test_deep_tailor_is_never_auto_assigned():
    for score in range(0, 101, 5):
        for referral in (False, True):
            for fresh in (False, True):
                assert assign_lane(PASSED, score, referral, fresh).lane != 3


def test_thresholds_are_named_constants():
    assert lanes.LANE_SKIP_BELOW == 60 and lanes.LANE_FAST_APPLY_MIN == 70


def test_model_task_is_valid_in_router_for_every_actionable_lane():
    for score, referral in [(80, False), (65, False), (10, True)]:
        d = assign_lane(PASSED, score, referral)
        assert d.model_task in TASK_TIERS
        assert route(d.model_task).task == d.model_task
    assert assign_lane(PASSED, 65, False).model_task == "tailor"
    assert assign_lane(PASSED, 80, False).model_task == "score"
    assert assign_lane(PASSED, 10, False).model_task is None
