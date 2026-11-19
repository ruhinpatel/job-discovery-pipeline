"""Lane routing: how much effort a surviving posting earns.

The score says how good a fit a row is; the lane says what to DO about it.
Lanes trade effort against payoff: below the keyword-match cliff extra
polish rarely changes the outcome, a referral bypasses the keyword screen
entirely, and a fresh posting rewards speed over polish.

    Lane 0 SKIP         gate failed, or score below LANE_SKIP_BELOW with no referral
    Lane 1 FAST-APPLY   referral, or score >= LANE_FAST_APPLY_MIN, or fresh and
                        score >= LANE_SKIP_BELOW. No tailoring.
    Lane 2 QUICK-TAILOR score in [LANE_SKIP_BELOW, LANE_FAST_APPLY_MIN), the band
                        where a short targeted edit can realistically cross the cliff
    Lane 3 DEEP-TAILOR  RESERVED. Never auto-assigned: it is the manual path for
                        target companies a person picks deliberately, so no score
                        threshold can grant it.

`model_task` bridges to router.py: the lane picks the effort, and
`router.route(model_task)` picks the model tier that performs it. Skipped rows
need no model call, so their model_task is None.

Pure function, no I/O. `is_fresh` defaults to False because the synthetic demo
data carries no timestamps; in production the feed's posting age is computed
upstream and passed in here.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.gates import GateResult

LANE_SKIP_BELOW = 60.0
LANE_FAST_APPLY_MIN = 70.0

LANE_NAMES = {0: "SKIP", 1: "FAST-APPLY", 2: "QUICK-TAILOR", 3: "DEEP-TAILOR"}


@dataclass(frozen=True)
class LaneDecision:
    lane: int
    name: str
    reason: str
    model_task: str | None


def _decision(lane: int, reason: str, model_task: str | None) -> LaneDecision:
    return LaneDecision(lane=lane, name=LANE_NAMES[lane], reason=reason, model_task=model_task)


def assign_lane(gate_result: GateResult, score: float, referral: bool,
                is_fresh: bool = False) -> LaneDecision:
    if not gate_result.passed:
        return _decision(0, f"failed gate {gate_result.failed_gate}: {gate_result.reason}", None)
    if referral:
        return _decision(1, "referral bypasses the keyword screen", "score")
    if score >= LANE_FAST_APPLY_MIN:
        return _decision(1, f"score {score:g} at or above {LANE_FAST_APPLY_MIN:g}", "score")
    if is_fresh and score >= LANE_SKIP_BELOW:
        return _decision(1, f"fresh posting, score {score:g}: speed beats polish", "score")
    if score >= LANE_SKIP_BELOW:
        return _decision(2, f"score {score:g} in the {LANE_SKIP_BELOW:g}-{LANE_FAST_APPLY_MIN:g} "
                            "band where a short tailor can cross the cliff", "tailor")
    return _decision(0, f"score {score:g} below {LANE_SKIP_BELOW:g} and no referral", None)
