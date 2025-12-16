"""Pipeline decision engine combining risk scoring, contextual bandit, and active questioning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml

from .bandit import LinUCBPolicy
from .questions import select_questions
from .risk import RiskModel


@dataclass
class DocumentProfile:
    is_scanned: Optional[bool] = None
    contains_dense_tables: Optional[bool] = None
    language: Optional[str] = None
    has_handwriting: Optional[bool] = None


@dataclass
class InputContext:
    industry: str = ""
    task_type: str = ""
    document_profile: Optional[DocumentProfile] = None
    user_preference: str = ""
    decision_impact: str = ""


@dataclass
class PipelinePlan:
    id: str
    risk_level: str
    config: Dict[str, str]
    target_score: float = 50.0


@dataclass
class PipelineDecisionResult:
    risk_score: float
    risk_level: str
    chosen_plan_id: str
    plan: Dict[str, str]
    confidence: float
    questions_to_ask: List[Dict]
    rationale: Dict[str, List[str]]
    debug: Dict

    def as_dict(self) -> Dict:
        return {
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "chosen_plan_id": self.chosen_plan_id,
            "plan": self.plan,
            "confidence": self.confidence,
            "questions_to_ask": self.questions_to_ask,
            "rationale": self.rationale,
            "debug": self.debug,
        }


def load_config(config_path: str) -> Dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _plan_from_config(entry: Dict) -> PipelinePlan:
    plan_config = {k: v for k, v in entry.items() if k not in {"id", "risk_level", "target_score"}}
    return PipelinePlan(
        id=entry["id"],
        risk_level=entry.get("risk_level", "LOW"),
        config=plan_config,
        target_score=entry.get("target_score", 50.0),
    )


def _feature_vector(features: Dict[str, float], config: Dict) -> List[float]:
    names = sorted(set(config["risk_weights"].get("linear", {}).keys()))
    # ensure interaction feature parts are represented for stability
    for interaction in config["risk_weights"].get("interactions", {}):
        for part in interaction.split("*"):
            names.append(part)
    unique_names = sorted(set(names))
    return [features.get(name, 0.0) for name in unique_names]


def decide_pipeline(
    context: InputContext,
    doc_profile: Optional[DocumentProfile] = None,
    config_path: str = "config/pipeline_decision.yaml",
    bandit_state_path: Optional[str] = None,
) -> PipelineDecisionResult:
    profile = doc_profile or context.document_profile or DocumentProfile()
    config = load_config(config_path)

    risk_model = RiskModel(config)
    risk_result = risk_model.score(context, profile)

    plans = [_plan_from_config(p) for p in config.get("plans", [])]
    state_path = bandit_state_path or config.get("bandit_state_path", "artifacts/bandit_state.json")
    bandit = LinUCBPolicy(plans=[p.__dict__ for p in plans], alpha=config.get("bandit_alpha", 1.5), state_path=state_path)
    feature_vector = _feature_vector(risk_result.features, config)
    plan_id, bandit_debug = bandit.select_arm(feature_vector, risk_result.level, risk_result.score)
    chosen_plan = next(p for p in plans if p.id == plan_id)

    bandit_confidence = _bandit_confidence(bandit_debug)
    confidence = max(0.0, min(1.0, 0.6 * risk_result.confidence + 0.4 * bandit_confidence))

    questions = select_questions(context, profile, risk_result.level, confidence, bandit_debug.scores, config)

    rationale = {
        "top_features": [f"{name}:{value:.2f}" for name, value in risk_result.contributions[:3]],
        "plan_choice": [
            "bandit" if bandit_debug.used_bandit else "cold_start",
            f"selected:{plan_id}",
        ],
    }

    debug = {
        "risk_contributions": risk_result.contributions,
        "bandit": {
            "used": bandit_debug.used_bandit,
            "scores": bandit_debug.scores,
            "chosen": bandit_debug.chosen,
        },
        "questions": questions,
        "feature_vector": feature_vector,
    }

    return PipelineDecisionResult(
        risk_score=risk_result.score,
        risk_level=risk_result.level,
        chosen_plan_id=plan_id,
        plan=chosen_plan.config,
        confidence=confidence,
        questions_to_ask=questions,
        rationale=rationale,
        debug=debug,
    )


def _bandit_confidence(bandit_debug) -> float:
    if not bandit_debug.used_bandit or len(bandit_debug.scores) < 2:
        return 0.5
    top1, top2 = bandit_debug.scores[0], bandit_debug.scores[1]
    denom = abs(top1[1]) + 1e-6
    margin = abs(top1[1] - top2[1]) / denom
    return max(0.0, min(1.0, margin))


__all__ = [
    "InputContext",
    "DocumentProfile",
    "PipelinePlan",
    "PipelineDecisionResult",
    "decide_pipeline",
]
