"""Cost-sensitive risk scoring model for pipeline decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class RiskResult:
    score: float
    level: str
    contributions: List[Tuple[str, float]]
    confidence: float
    features: Dict[str, float]


class RiskModel:
    def __init__(self, config: Dict):
        self.config = config
        self.weights = config["risk_weights"].get("linear", {})
        self.interaction_weights = config["risk_weights"].get("interactions", {})
        self.industry_prior = config.get("industry_prior", {})
        self.cost_matrix = config.get("cost_matrix", {})
        self.thresholds = config.get("thresholds", {})

    def featurize(self, context, doc_profile) -> Dict[str, float]:
        industry = (context.industry or "").lower().strip()
        task = (context.task_type or "").lower().strip()
        decision_impact = (context.decision_impact or "").lower().strip() or task
        user_pref = (context.user_preference or "").lower().strip()
        lang = (doc_profile.language or "").lower().strip()
        features: Dict[str, float] = {}
        if industry:
            features[f"industry_{industry}"] = 1.0
        if task:
            features[f"task_{task}"] = 1.0
        if decision_impact:
            features[f"decision_impact_{decision_impact}"] = 1.0
        if user_pref:
            features[f"user_preference_{user_pref}"] = 1.0
        features["doc_scanned"] = 1.0 if doc_profile.is_scanned else 0.0
        features["doc_dense_tables"] = 1.0 if doc_profile.contains_dense_tables else 0.0
        features["doc_handwriting"] = 1.0 if doc_profile.has_handwriting else 0.0
        features["language_non_en"] = 0.0 if not lang or lang in {"en", "english"} else 1.0
        return features

    def _interaction_value(self, interaction: str, features: Dict[str, float]) -> float:
        parts = interaction.split("*")
        value = 1.0
        for part in parts:
            value *= features.get(part, 0.0)
        return value

    def _apply_costs(self, base_score: float, context) -> float:
        fn = float(self.cost_matrix.get("false_negative", 1))
        fp = float(self.cost_matrix.get("false_positive", 1))
        catastrophic = float(self.cost_matrix.get("catastrophic", 0))
        criticality = 1.0
        if (context.decision_impact or "").lower().strip() in {"regulatory", "financial"}:
            criticality += catastrophic / 50.0
        asymmetry = (fn + catastrophic / 10.0) / max(fp, 1.0)
        return base_score * asymmetry * criticality

    def score(self, context, doc_profile) -> RiskResult:
        features = self.featurize(context, doc_profile)
        contributions: List[Tuple[str, float]] = []
        linear_sum = 0.0
        for name, weight in self.weights.items():
            value = features.get(name, 0.0)
            contribution = weight * value
            linear_sum += contribution
            contributions.append((name, contribution))

        for name, weight in self.interaction_weights.items():
            value = self._interaction_value(name, features)
            contribution = weight * value
            linear_sum += contribution
            contributions.append((name, contribution))

        industry = (context.industry or "").lower().strip()
        prior = self.industry_prior.get(industry, 0)
        if prior:
            linear_sum += prior
            contributions.append(("industry_prior", prior))

        cost_adjusted = self._apply_costs(linear_sum, context)
        risk_score = max(0.0, min(cost_adjusted, 100.0))
        level = self.resolve_level(risk_score)
        confidence = self._confidence(risk_score)
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        return RiskResult(
            score=risk_score,
            level=level,
            contributions=contributions,
            confidence=confidence,
            features=features,
        )

    def resolve_level(self, score: float) -> str:
        high = self.thresholds.get("high", 75)
        medium = self.thresholds.get("medium", 45)
        if score >= high:
            return "HIGH"
        if score >= medium:
            return "MED"
        return "LOW"

    def _confidence(self, score: float) -> float:
        high = self.thresholds.get("high", 75)
        medium = self.thresholds.get("medium", 45)
        low = self.thresholds.get("low", 0)
        distances = []
        for bound in [low, medium, high]:
            distances.append(abs(score - bound))
        nearest = min(distances)
        return max(0.0, min(1.0, 1 - nearest / 100.0))


__all__ = ["RiskModel", "RiskResult"]
