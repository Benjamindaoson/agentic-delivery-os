"""Active learning question selector based on uncertainty and impact."""

from __future__ import annotations

from typing import Dict, List


def _is_feature_missing(context, doc_profile, feature: str) -> bool:
    if hasattr(doc_profile, feature):
        value = getattr(doc_profile, feature)
    elif hasattr(context, feature):
        value = getattr(context, feature)
    else:
        return True
    if isinstance(value, bool):
        return False
    return value in (None, "", [])


def select_questions(
    context,
    doc_profile,
    risk_level: str,
    confidence: float,
    bandit_debug: Dict,
    config: Dict,
) -> List[Dict]:
    q_cfg = config.get("questions", {})
    pool = q_cfg.get("question_pool", [])
    max_questions = int(q_cfg.get("max_questions", 3))
    conf_threshold = float(q_cfg.get("conf_threshold", 0.65))
    bandit_gap_threshold = float(q_cfg.get("bandit_gap_threshold", 0.15))

    top_scores: List[Dict] = []
    uncertainty = max(0.0, 1.0 - confidence)
    bandit_gap = bandit_debug.get("gap", 1.0)
    bandit_uncertainty = max(0.0, bandit_gap_threshold - bandit_gap)

    should_trigger = (confidence < conf_threshold) or (
        bandit_uncertainty > 0 and risk_level != "LOW"
    ) or (risk_level == "HIGH")
    if not should_trigger:
        return []

    for q in pool:
        related_features = q.get("related_features", [])
        missing = any(_is_feature_missing(context, doc_profile, feat) for feat in related_features)
        impact = float(q.get("expected_impact_weight", 0.0))
        score = impact * (uncertainty + bandit_uncertainty)

        if risk_level == "HIGH" and q.get("required_for_high_risk", False) and missing:
            score += 1.0
        elif missing:
            score += 0.2 * impact

        if score > 0:
            top_scores.append({"id": q.get("id"), "text": q.get("text"), "score": score})

    top_scores.sort(key=lambda item: item["score"], reverse=True)
    return top_scores[:max_questions]

