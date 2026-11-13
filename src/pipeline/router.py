"""Cost-aware model routing.

Scoring every posting is high-frequency and low-stakes, so it should run on
the cheapest model that can do it; generating tailored content is
low-frequency and higher-stakes, so it earns a larger model. This module
holds that routing decision as data, separate from the scoring logic itself,
so the policy can be inspected or changed without touching scorer.py.

No model is actually called here - this returns a routing decision, which the
real system hands to whichever client wraps the chosen tier.
"""

from __future__ import annotations

from dataclasses import dataclass

# Illustrative only: relative order (small < medium < large), not a quote
# from any provider's pricing.
_COST_PER_CALL_USD = {"small": 0.001, "medium": 0.01, "large": 0.08}

TASK_TIERS: dict[str, dict[str, str]] = {
    "score": {
        "tier": "small",
        "rationale": "runs once per posting; a rough fit estimate is enough to rank the queue",
    },
    "tailor": {
        "tier": "medium",
        "rationale": "runs once per posting a person chose to pursue; bounded edit, not free generation",
    },
    "deep_tailor": {
        "tier": "large",
        "rationale": "runs rarely, only for postings worth the most careful generation",
    },
}


@dataclass(frozen=True)
class RoutingDecision:
    task: str
    tier: str
    rationale: str
    cost_per_call_usd: float


def route(task: str) -> RoutingDecision:
    try:
        entry = TASK_TIERS[task]
    except KeyError:
        raise ValueError(f"unknown task {task!r}; expected one of {sorted(TASK_TIERS)}") from None
    tier = entry["tier"]
    return RoutingDecision(
        task=task, tier=tier, rationale=entry["rationale"],
        cost_per_call_usd=_COST_PER_CALL_USD[tier],
    )


def estimate_batch_cost_usd(task: str, call_count: int) -> float:
    """Cost of running `task` `call_count` times at its routed tier. Lets a
    reviewer see the payoff of routing high-volume work to a cheap tier."""
    if call_count < 0:
        raise ValueError("call_count must be >= 0")
    return route(task).cost_per_call_usd * call_count
