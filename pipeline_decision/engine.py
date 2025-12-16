"""Unified pipeline decision engine using risk scoring, bandit selection, and active questions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .bandit import LinUCB
from .questions import select_questions
from .risk import RiskAssessment, score_risk


@dataclass(frozen=True)
class DocumentProfile:
    is_scanned: bool = False
    contains_dense_tables: bool = False
    language: str = ""
    has_handwriting: bool = False
    data_sensitivity: str = ""


@dataclass(frozen=True)
class InputContext:
    industry: str = ""
    task_type: str = ""
    document_profile: DocumentProfile = DocumentProfile()
    user_preference: str = ""
    decision_impact: str = ""


@dataclass
class PipelinePlan:
    plan_id: str
    risk_level: str
    parsing_strategy: str
    chunking_strategy: str
    embedding_strategy: str
    retrieval_strategy: str
    rerank_strategy: str
    hitl_policy: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "plan_id": self.plan_id,
            "risk_level": self.risk_level,
            "parsing_strategy": self.parsing_strategy,
            "chunking_strategy": self.chunking_strategy,
            "embedding_strategy": self.embedding_strategy,
            "retrieval_strategy": self.retrieval_strategy,
            "rerank_strategy": self.rerank_strategy,
            "hitl_policy": self.hitl_policy,
        }


@dataclass
class PipelineDecisionResult:
    risk_score: float
    risk_level: str
    chosen_plan_id: str
    plan: Dict[str, str]
    confidence: float
    questions_to_ask: List[Dict]
    rationale: List[str]
    debug: Dict

    def to_dict(self) -> Dict:
        """Return a fully JSON-serializable representation of the decision."""

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

    def __iter__(self):  # pragma: no cover - convenience for callers expecting dict-like behavior
        return iter(self.to_dict().items())


_CONFIG_CACHE: Optional[Dict] = None


def load_config(config_path: Optional[str] = None) -> Dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and config_path is None:
        return _CONFIG_CACHE
    path = Path(config_path or "config/pipeline_decision.yaml")
    with path.open("r") as f:
        config = yaml.safe_load(f)
    if config_path is None:
        _CONFIG_CACHE = config
    return config


def _plans_from_config(config: Dict) -> Dict[str, PipelinePlan]:
    plans = {}
    for plan_cfg in config.get("plans", []):
        plan = PipelinePlan(
            plan_id=plan_cfg["id"],
            risk_level=plan_cfg.get("risk_level", "MEDIUM"),
            parsing_strategy=plan_cfg["parsing_strategy"],
            chunking_strategy=plan_cfg["chunking_strategy"],
            embedding_strategy=plan_cfg["embedding_strategy"],
            retrieval_strategy=plan_cfg["retrieval_strategy"],
            rerank_strategy=plan_cfg["rerank_strategy"],
            hitl_policy=plan_cfg["hitl_policy"],
        )
        plans[plan.plan_id] = plan
    return plans


def _confidence_from_score(score: float, thresholds: Dict[str, float], bandit_gap: float) -> float:
    low_t = float(thresholds.get("low", 25))
    med_t = float(thresholds.get("medium", 50))
    high_t = float(thresholds.get("high", 75))

    if score < med_t:
        margin = med_t - score
        base_conf = min(1.0, margin / max(med_t, 1.0))
    elif score < high_t:
        span = max(high_t - med_t, 1.0)
        margin = min(score - med_t, high_t - score)
        base_conf = max(0.2, min(1.0, margin / span))
    else:
        margin = score - high_t
        base_conf = min(1.0, margin / max(100.0 - high_t, 1.0))

    bandit_uncertainty = max(0.0, 0.1 - bandit_gap)
    return max(0.0, min(1.0, base_conf - bandit_uncertainty))


def _bandit_vector(context: InputContext, doc_profile: DocumentProfile, risk_score: float) -> List[float]:
    doc_complexity = float(
        int(doc_profile.is_scanned) + int(doc_profile.contains_dense_tables) + int(doc_profile.has_handwriting)
    )
    return [
        1.0,
        risk_score / 100.0,
        doc_complexity / 5.0,
        1.0 if (doc_profile.language or "").lower() not in {"", "en", "english"} else 0.0,
        1.0 if (context.user_preference or "").lower() == "quality" else 0.0,
    ]


def _fallback_plan_id(risk_level: str, plans: Dict[str, PipelinePlan]) -> str:
    for plan in plans.values():
        if plan.risk_level.upper() == risk_level.upper():
            return plan.plan_id
    return next(iter(plans.keys()))


def decide_pipeline(
    context: InputContext,
    doc_profile: Optional[DocumentProfile] = None,
    *,
    config_path: Optional[str] = None,
    bandit_state_path: Optional[str] = None,
    reward: Optional[float] = None,
) -> PipelineDecisionResult:
    doc_profile = doc_profile or context.document_profile
    config = load_config(config_path)
    plans = _plans_from_config(config)

    risk_assessment: RiskAssessment = score_risk(context, doc_profile, config)
    thresholds = config.get("risk", {}).get("thresholds", {})

    vector = _bandit_vector(context, doc_profile, risk_assessment.score)
    bandit_cfg = config.get("bandit", {})
    state_path = Path(bandit_state_path or bandit_cfg.get("state_path", "artifacts/bandit_state.json"))
    bandit = LinUCB(
        arms=list(plans.keys()),
        alpha=float(bandit_cfg.get("alpha", 1.0)),
        state_path=state_path,
        context_dim=len(vector),
    )

    chosen_plan_id, bandit_debug = bandit.select_arm(vector)
    cold_start = not state_path.exists()
    if cold_start:
        chosen_plan_id = _fallback_plan_id(risk_assessment.level, plans)
    elif reward is not None:
        bandit.update(vector, chosen_plan_id, float(reward))

    chosen_plan = plans[chosen_plan_id]
    confidence = _confidence_from_score(risk_assessment.score, thresholds, bandit_debug.gap)
    questions = select_questions(
        context,
        doc_profile,
        risk_assessment.level,
        confidence,
        bandit_debug.__dict__,
        config,
    )

    rationale = list(risk_assessment.rationale)
    rationale.append(f"Plan {chosen_plan_id} chosen via {'bandit' if bandit_debug.used_bandit and not cold_start else 'risk fallback'}")

    debug = {
        "risk": {
            "score_before_threshold": risk_assessment.score,
            "contributions": risk_assessment.contributions,
        },
        "bandit": {
            "used_bandit": bandit_debug.used_bandit and not cold_start,
            "top_scores": bandit_debug.top_scores,
            "gap": bandit_debug.gap,
        },
        "questions": questions,
    }

    return PipelineDecisionResult(
        risk_score=risk_assessment.score,
        risk_level=risk_assessment.level,
        chosen_plan_id=chosen_plan.plan_id,
        plan=chosen_plan.as_dict(),
        confidence=confidence,
        questions_to_ask=questions,
        rationale=rationale,
        debug=debug,
    )


def example_input_contexts() -> List[InputContext]:
    return [
        InputContext(
            industry="education",
            task_type="qa",
            document_profile=DocumentProfile(language="en"),
            user_preference="speed",
            decision_impact="informational",
        ),
        InputContext(
            industry="public_sector",
            task_type="research",
            document_profile=DocumentProfile(is_scanned=False, contains_dense_tables=True, language="en"),
            user_preference="speed",
            decision_impact="operational",
        ),
        InputContext(
            industry="finance",
            task_type="compliance",
            document_profile=DocumentProfile(is_scanned=True, contains_dense_tables=True, has_handwriting=True, language="fr"),
            user_preference="quality",
            decision_impact="regulatory",
        ),
    ]


def example_pipeline_plans() -> List[Dict[str, Dict[str, str]]]:
    plans = []
    for context in example_input_contexts():
        decision = decide_pipeline(context)
        plans.append({"context": context, "result": json.loads(json.dumps(decision, default=lambda o: o.__dict__))})
    return plans

