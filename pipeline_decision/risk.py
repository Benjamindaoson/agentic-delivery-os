"""Cost-sensitive risk scoring utilities for pipeline decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class RiskAssessment:
    score: float
    level: str
    rationale: List[str]
    contributions: Dict[str, float]


DEFAULT_TASK_RISK = {
    "compliance": 3.0,
    "decision": 2.5,
    "research": 2.0,
    "qa": 1.0,
}


DEFAULT_IMPACT_RISK = {
    "regulatory": 3.0,
    "financial": 2.5,
    "operational": 2.0,
    "informational": 1.0,
}


def featurize(context, doc_profile, config: Dict) -> Dict[str, float]:
    """Build a deterministic feature vector used by the risk model."""

    industry_prior = config.get("industry_prior", {})
    industry_key = (context.industry or "").lower()
    features: Dict[str, float] = {
        "industry_prior": float(industry_prior.get(industry_key, industry_prior.get("default", 1))),
    }

    task_map = config.get("task_risk", DEFAULT_TASK_RISK)
    task_key = (context.task_type or "").lower()
    features["task_criticality"] = float(task_map.get(task_key, task_map.get("default", 1.0)))

    impact_map = config.get("impact_risk", DEFAULT_IMPACT_RISK)
    impact_key = (context.decision_impact or task_key)
    features["decision_impact"] = float(impact_map.get(impact_key.lower(), impact_map.get("default", 1.0)))

    features["doc_complexity"] = float(
        int(doc_profile.is_scanned)
        + int(doc_profile.contains_dense_tables)
        + int(doc_profile.has_handwriting)
    )
    features["handwriting"] = 1.0 if doc_profile.has_handwriting else 0.0
    features["dense_tables"] = 1.0 if doc_profile.contains_dense_tables else 0.0
    features["language_non_en"] = 0.0 if (doc_profile.language or "").lower() in {"", "en", "english"} else 1.0

    preference = (context.user_preference or "").lower()
    features["user_pref_quality"] = 1.0 if preference == "quality" else 0.0
    features["user_pref_speed"] = 1.0 if preference == "speed" else 0.0
    features["user_pref_cost"] = 1.0 if preference == "cost" else 0.0

    return features


def _apply_weights(features: Dict[str, float], weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    contributions: Dict[str, float] = {}
    base = 0.0
    for key, value in features.items():
        weight = float(weights.get(key, 0.0))
        contrib = weight * value
        contributions[key] = contrib
        base += contrib
    return base, contributions


def _apply_interactions(features: Dict[str, float], interaction_weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    contributions: Dict[str, float] = {}
    total = 0.0
    for pair, weight in interaction_weights.items():
        parts = pair.split("|")
        if len(parts) != 2:
            continue
        a, b = parts
        if a not in features or b not in features:
            continue
        contrib = float(weight) * features[a] * features[b]
        contributions[pair] = contrib
        total += contrib
    return total, contributions


def score_risk(context, doc_profile, config: Dict) -> RiskAssessment:
    risk_cfg = config.get("risk", {})
    thresholds = risk_cfg.get(
        "thresholds", {"low": 25, "medium": 50, "high": 75}
    )
    features = featurize(context, doc_profile, risk_cfg)
    base, base_contrib = _apply_weights(features, risk_cfg.get("risk_weights", {}))
    interaction_total, interaction_contrib = _apply_interactions(
        features, risk_cfg.get("interaction_weights", {})
    )

    score_before_cost = base + interaction_total
    cost_matrix = risk_cfg.get("cost_matrix", {"fp": 5.0, "fn": 10.0, "critical": 15.0})
    avg_error_cost = (float(cost_matrix.get("fp", 5.0)) + float(cost_matrix.get("fn", 10.0))) / 40.0
    critical_component = float(cost_matrix.get("critical", 15.0)) * (features.get("doc_complexity", 0.0) / 10.0)
    expected_cost = score_before_cost * (1.0 + avg_error_cost) + critical_component
    score = max(0.0, min(expected_cost, 100.0))

    if score >= thresholds.get("high", 75):
        level = "HIGH"
    elif score >= thresholds.get("medium", 50):
        level = "MEDIUM"
    else:
        level = "LOW"

    merged_contrib = {**base_contrib, **interaction_contrib}
    top_features = sorted(merged_contrib.items(), key=lambda kv: abs(kv[1]), reverse=True)
    rationale = [f"{name}: {contrib:.2f}" for name, contrib in top_features[:3]]

    return RiskAssessment(score=score, level=level, rationale=rationale, contributions=merged_contrib)

