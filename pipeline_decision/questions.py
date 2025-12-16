"""Active learning question selector based on uncertainty and impact."""
from __future__ import annotations

from typing import Dict, List


def select_questions(
    context,
    doc_profile,
    risk_level: str,
    confidence: float,
    bandit_scores: List[tuple],
    config: Dict,
) -> List[Dict]:
    question_pool = config.get("question_pool", [])
    conf_threshold = config.get("question_conf_threshold", 0.65)
    max_questions = 3
    base_uncertainty = max(0.0, 1 - confidence)
    bandit_uncertainty = 0.0
    if len(bandit_scores) >= 2:
        top1, top2 = bandit_scores[0], bandit_scores[1]
        denom = abs(top1[1]) + 1e-6
        bandit_margin = abs(top1[1] - top2[1]) / max(denom, 1e-6)
        bandit_uncertainty = max(0.0, 1 - min(bandit_margin, 1.0))
    candidate_scores = []
    missing_flags = _missing_feature_flags(doc_profile)
    triggers_high_risk = risk_level == "HIGH"
    for q in question_pool:
        related_missing = any(missing_flags.get(f, False) for f in q.get("related_features", []))
        uncertainty_signal = base_uncertainty + bandit_uncertainty
        score = q.get("expected_impact_weight", 1.0) * max(uncertainty_signal, 0.05)
        if (confidence < conf_threshold or related_missing) and q.get("required_for_high_risk") and triggers_high_risk:
            score += 1.5
        if score > 0:
            candidate_scores.append((q, score, related_missing))
    candidate_scores.sort(key=lambda t: t[1], reverse=True)
    selected = []
    for item in candidate_scores:
        q, score, missing = item
        if len(selected) >= max_questions:
            break
        if confidence >= conf_threshold and not missing and risk_level != "HIGH":
            continue
        q_copy = dict(q)
        q_copy["score"] = score
        q_copy["related_missing"] = missing
        selected.append(q_copy)
    return selected


def _missing_feature_flags(doc_profile) -> Dict[str, bool]:
    return {
        "doc_scanned": doc_profile.is_scanned is None,
        "doc_dense_tables": doc_profile.contains_dense_tables is None,
        "doc_handwriting": doc_profile.has_handwriting is None,
        "language_non_en": doc_profile.language is None or doc_profile.language == "",
    }


__all__ = ["select_questions"]
