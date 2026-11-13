import pytest

from pipeline.router import estimate_batch_cost_usd, route


def test_score_routes_to_small_tier():
    decision = route("score")
    assert decision.tier == "small"


def test_deep_tailor_routes_to_large_tier():
    decision = route("deep_tailor")
    assert decision.tier == "large"


def test_small_tier_is_cheaper_than_large_tier():
    assert route("score").cost_per_call_usd < route("deep_tailor").cost_per_call_usd


def test_unknown_task_raises():
    with pytest.raises(ValueError):
        route("not_a_real_task")


def test_batch_cost_scales_with_volume():
    assert estimate_batch_cost_usd("score", 1000) > estimate_batch_cost_usd("score", 10)


def test_batch_cost_rejects_negative_count():
    with pytest.raises(ValueError):
        estimate_batch_cost_usd("score", -1)


def test_routing_high_frequency_to_small_beats_routing_to_large():
    """The headline claim: scoring a large batch on the small tier costs far
    less than running the same batch on the large tier."""
    cheap = estimate_batch_cost_usd("score", 500)
    expensive_if_misrouted = route("deep_tailor").cost_per_call_usd * 500
    assert cheap < expensive_if_misrouted / 10
