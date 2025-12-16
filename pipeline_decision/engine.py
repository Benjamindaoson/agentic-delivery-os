"""Decision-only Pipeline Plan generator based on contextual risk assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ParsingStrategy(str, Enum):
    LIGHTWEIGHT = "lightweight"
    HYBRID = "hybrid"
    MAXIMUM_FIDELITY = "maximum_fidelity"


class ChunkingStrategy(str, Enum):
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    ALGORITHMIC = "algorithmic"


class EmbeddingStrategy(str, Enum):
    SINGLE = "single"
    MULTI = "multi"
    ADAPTIVE = "adaptive"


class RetrievalStrategy(str, Enum):
    VECTOR_ONLY = "vector_only"
    HYBRID = "hybrid"
    MULTI_STAGE = "multi_stage"


class RerankStrategy(str, Enum):
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    MULTI_PASS = "multi_pass"


class HitlPolicy(str, Enum):
    DISABLED = "disabled"
    CONDITIONAL = "conditional"
    MANDATORY = "mandatory"


@dataclass(frozen=True)
class DocumentProfile:
    """Describes document traits that affect processing complexity."""

    is_scanned: bool = False
    contains_dense_tables: bool = False
    language: str = ""
    has_handwriting: bool = False


@dataclass(frozen=True)
class InputContext:
    """Inputs used to decide pipeline behavior."""

    industry: str = ""
    task_type: str = ""
    document_profile: DocumentProfile = DocumentProfile()
    user_preference: str = ""
    decision_impact: str = ""  # e.g., operational, financial, regulatory


@dataclass(frozen=True)
class PipelinePlan:
    """Selected pipeline plan with strategies only."""

    risk_level: RiskLevel
    parsing_strategy: ParsingStrategy
    chunking_strategy: ChunkingStrategy
    embedding_strategy: EmbeddingStrategy
    retrieval_strategy: RetrievalStrategy
    rerank_strategy: RerankStrategy
    hitl_policy: HitlPolicy

    def as_dict(self) -> Dict[str, str]:
        return {
            "risk_level": self.risk_level.value,
            "parsing_strategy": self.parsing_strategy.value,
            "chunking_strategy": self.chunking_strategy.value,
            "embedding_strategy": self.embedding_strategy.value,
            "retrieval_strategy": self.retrieval_strategy.value,
            "rerank_strategy": self.rerank_strategy.value,
            "hitl_policy": self.hitl_policy.value,
        }


# Risk scoring constants kept explicit for traceability.
INDUSTRY_PRIOR = {
    "finance": 3,
    "fintech": 3,
    "health": 3,
    "healthcare": 3,
    "pharma": 3,
    "legal": 3,
    "public_sector": 2,
    "energy": 2,
}

TASK_CRITICALITY = {
    "compliance": 3,
    "decision": 2,
    "research": 2,
    "qa": 1,
}

DECISION_IMPACT = {
    "regulatory": 3,
    "financial": 3,
    "operational": 2,
    "informational": 1,
}

DOCUMENT_COMPLEXITY_BONUS = 2
HANDWRITING_COMPLEXITY_BONUS = 1
DENSE_TABLE_COMPLEXITY_BONUS = 1

USER_OVERRIDE = {
    "quality": 1,
    "speed": -1,
    "cost": -1,
}

HIGH_RISK_THRESHOLD = 7
MEDIUM_RISK_THRESHOLD = 4
MIN_RISK_SCORE = 0
MAX_RISK_SCORE = 9


def normalized_score(score: int) -> int:
    return max(MIN_RISK_SCORE, min(score, MAX_RISK_SCORE))


def industry_risk(industry: str) -> int:
    key = industry.lower().strip()
    return INDUSTRY_PRIOR.get(key, 1 if key else 0)


def task_risk(task_type: str) -> int:
    key = task_type.lower().strip()
    return TASK_CRITICALITY.get(key, 1 if key else 0)


def document_risk(profile: DocumentProfile) -> int:
    score = 0
    if profile.is_scanned:
        score += DOCUMENT_COMPLEXITY_BONUS
    if profile.contains_dense_tables:
        score += DENSE_TABLE_COMPLEXITY_BONUS
    if profile.has_handwriting:
        score += HANDWRITING_COMPLEXITY_BONUS
    if profile.language.lower() not in {"", "en", "english"}:
        score += 1
    return score


def decision_impact_risk(impact: str, fallback_task_type: str) -> int:
    key = impact.lower().strip()
    if not key:
        key = fallback_task_type.lower().strip()
    return DECISION_IMPACT.get(key, 1 if key else 0)


def apply_user_override(base_score: int, preference: str) -> int:
    key = preference.lower().strip()
    adjustment = USER_OVERRIDE.get(key, 0)
    return normalized_score(base_score + adjustment)


def score_context(context: InputContext) -> int:
    score = 0
    score += industry_risk(context.industry)
    score += task_risk(context.task_type)
    score += document_risk(context.document_profile)
    score += decision_impact_risk(context.decision_impact, context.task_type)
    return apply_user_override(score, context.user_preference)


def resolve_risk_level(score: int) -> RiskLevel:
    if score >= HIGH_RISK_THRESHOLD:
        return RiskLevel.HIGH
    if score >= MEDIUM_RISK_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


BASELINE_PLAN = {
    RiskLevel.LOW: PipelinePlan(
        risk_level=RiskLevel.LOW,
        parsing_strategy=ParsingStrategy.LIGHTWEIGHT,
        chunking_strategy=ChunkingStrategy.SEMANTIC,
        embedding_strategy=EmbeddingStrategy.SINGLE,
        retrieval_strategy=RetrievalStrategy.VECTOR_ONLY,
        rerank_strategy=RerankStrategy.NONE,
        hitl_policy=HitlPolicy.DISABLED,
    ),
    RiskLevel.MEDIUM: PipelinePlan(
        risk_level=RiskLevel.MEDIUM,
        parsing_strategy=ParsingStrategy.HYBRID,
        chunking_strategy=ChunkingStrategy.HYBRID,
        embedding_strategy=EmbeddingStrategy.ADAPTIVE,
        retrieval_strategy=RetrievalStrategy.HYBRID,
        rerank_strategy=RerankStrategy.CROSS_ENCODER,
        hitl_policy=HitlPolicy.CONDITIONAL,
    ),
    RiskLevel.HIGH: PipelinePlan(
        risk_level=RiskLevel.HIGH,
        parsing_strategy=ParsingStrategy.MAXIMUM_FIDELITY,
        chunking_strategy=ChunkingStrategy.ALGORITHMIC,
        embedding_strategy=EmbeddingStrategy.MULTI,
        retrieval_strategy=RetrievalStrategy.MULTI_STAGE,
        rerank_strategy=RerankStrategy.MULTI_PASS,
        hitl_policy=HitlPolicy.MANDATORY,
    ),
}


def adjusted_for_preference(plan: PipelinePlan, preference: str, risk_level: RiskLevel) -> PipelinePlan:
    # High risk plans are immutable by preference to respect safeguards.
    if risk_level == RiskLevel.HIGH:
        return plan

    key = preference.lower().strip()

    if key == "speed":
        return PipelinePlan(
            risk_level=plan.risk_level,
            parsing_strategy=ParsingStrategy.LIGHTWEIGHT,
            chunking_strategy=plan.chunking_strategy,
            embedding_strategy=EmbeddingStrategy.SINGLE,
            retrieval_strategy=RetrievalStrategy.VECTOR_ONLY,
            rerank_strategy=RerankStrategy.NONE,
            hitl_policy=plan.hitl_policy,
        )

    if key == "cost":
        return PipelinePlan(
            risk_level=plan.risk_level,
            parsing_strategy=plan.parsing_strategy,
            chunking_strategy=ChunkingStrategy.SEMANTIC,
            embedding_strategy=EmbeddingStrategy.SINGLE,
            retrieval_strategy=RetrievalStrategy.VECTOR_ONLY,
            rerank_strategy=RerankStrategy.NONE,
            hitl_policy=plan.hitl_policy,
        )

    if key == "quality":
        return PipelinePlan(
            risk_level=plan.risk_level,
            parsing_strategy=max(plan.parsing_strategy, ParsingStrategy.HYBRID, key=lambda s: list(ParsingStrategy).index(s)),
            chunking_strategy=max(plan.chunking_strategy, ChunkingStrategy.HYBRID, key=lambda s: list(ChunkingStrategy).index(s)),
            embedding_strategy=max(plan.embedding_strategy, EmbeddingStrategy.ADAPTIVE, key=lambda s: list(EmbeddingStrategy).index(s)),
            retrieval_strategy=max(plan.retrieval_strategy, RetrievalStrategy.HYBRID, key=lambda s: list(RetrievalStrategy).index(s)),
            rerank_strategy=max(plan.rerank_strategy, RerankStrategy.CROSS_ENCODER, key=lambda s: list(RerankStrategy).index(s)),
            hitl_policy=max(plan.hitl_policy, HitlPolicy.CONDITIONAL, key=lambda s: list(HitlPolicy).index(s)),
        )

    return plan


def decide_pipeline(context: InputContext) -> PipelinePlan:
    score = normalized_score(score_context(context))
    risk_level = resolve_risk_level(score)
    base_plan = BASELINE_PLAN[risk_level]
    return adjusted_for_preference(base_plan, context.user_preference, risk_level)


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
        plan = decide_pipeline(context)
        plans.append({"context": context, "plan": plan.as_dict()})
    return plans
