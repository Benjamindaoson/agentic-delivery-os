"""
Discovery Reward computation for controlled exploration.

Components:
- info_gain: based on shadow_diff divergence / attribution entropy
- novelty: new pattern coverage
- coverage_gain: golden set failure class coverage
- success_uplift: candidate vs active uplift
- penalty: cost/latency regressions or evidence drop
"""
import math
from dataclasses import dataclass, asdict
from typing import Dict, Any
from runtime.artifacts.artifact_schema import DEFAULT_SCHEMA_VERSION


@dataclass
class RewardResult:
    schema_version: str
    reward_total: float
    components: Dict[str, float]
    attribution_used: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_reward(
    shadow_diff: Dict[str, Any],
    golden_coverage_gain: float,
    attribution_weights: Dict[str, float],
    evidence_usage_rate: float,
    cost_delta: float,
    latency_delta: float,
) -> RewardResult:
    # info gain: divergence of decisions / success delta
    success_delta = shadow_diff.get("success_delta", 0)
    decision_divergence = 1.0 if shadow_diff.get("decision_divergence") else 0.0
    info_gain = 0.5 * decision_divergence + 0.5 * max(success_delta, 0)

    # novelty: encourage lower evidence reuse
    novelty = max(0.0, 1 - evidence_usage_rate)

    # coverage gain from golden
    coverage_gain = golden_coverage_gain

    # success uplift
    success_uplift = max(0.0, shadow_diff.get("success_delta", 0))

    # penalty for cost/latency regressions
    penalty = 0.0
    penalty += max(0.0, cost_delta)
    penalty += max(0.0, latency_delta / 3000)  # normalize
    penalty += 0.2 if evidence_usage_rate < 0.3 else 0.0

    base = info_gain + novelty + coverage_gain + success_uplift - penalty
    # weight with attribution focus
    focus_weight = max(attribution_weights.values()) if attribution_weights else 1.0
    reward_total = round(base * focus_weight, 4)

    components = {
        "info_gain": round(info_gain, 4),
        "novelty": round(novelty, 4),
        "coverage_gain": round(coverage_gain, 4),
        "success_uplift": round(success_uplift, 4),
        "penalty": round(penalty, 4),
    }

    return RewardResult(
        schema_version=DEFAULT_SCHEMA_VERSION,
        reward_total=reward_total,
        components=components,
        attribution_used=attribution_weights,
    )



