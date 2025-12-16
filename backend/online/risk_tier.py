"""
Risk-Tier engine for Online Pipeline (Phase 8 · P2)

Tiers:
  R0 – low risk information lookup
  R1 – general knowledge
  R2 – business advice
  R3 – high risk (finance / compliance)
  R4 – must not be auto-answered (human-only)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


RISK_TIERS = ("R0", "R1", "R2", "R3", "R4")


@dataclass
class RiskTierDecision:
    risk_tier: str
    source: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _infer_from_profile(profile: str) -> Optional[str]:
    profile = (profile or "").lower()
    if profile == "finance":
        return "R3"
    if profile == "edu":
        return "R1"
    if profile == "general":
        return "R1"
    return None


FINANCE_KEYWORDS = ("stock", "bond", "equity", "loan", "利率", "收益率", "股票", "期货")
HIGH_RISK_KEYWORDS = ("guarantee", "legal", "compliance", "合规", "担保", "违法", "违规")
BLOCK_KEYWORDS = ("fraud", "洗钱", "money laundering", "terrorism", "恐怖主义")


def _infer_from_query(query: str) -> Optional[str]:
    q = (query or "").lower()
    if any(k in q for k in BLOCK_KEYWORDS):
        return "R4"
    if any(k in q for k in HIGH_RISK_KEYWORDS):
        return "R3"
    if any(k in q for k in FINANCE_KEYWORDS):
        return "R3"
    if len(q) > 200:
        return "R2"
    return "R0"


def determine_risk_tier(
    profile: Optional[str],
    query: str,
    explicit_tier: Optional[str] = None,
) -> RiskTierDecision:
    """
    Determine Risk-Tier based on:
    1) Explicit user-provided tier (highest priority)
    2) Profile (finance / edu / general)
    3) Query semantics (fallback)
    """
    # 1) explicit override
    if explicit_tier in RISK_TIERS:
        return RiskTierDecision(risk_tier=explicit_tier, source="explicit", confidence=0.99)

    # 2) profile-based
    profile_tier = _infer_from_profile(profile or "")
    query_tier = _infer_from_query(query or "")

    if profile_tier and query_tier:
        # Take the stricter (higher) tier between profile and query
        order = {t: i for i, t in enumerate(RISK_TIERS)}
        chosen = profile_tier if order[profile_tier] >= order[query_tier] else query_tier
        source = "profile+query"
        confidence = 0.9
    elif profile_tier:
        chosen = profile_tier
        source = "profile"
        confidence = 0.8
    else:
        chosen = query_tier or "R1"
        source = "query"
        confidence = 0.7

    return RiskTierDecision(risk_tier=chosen, source=source, confidence=confidence)


def build_online_plans(decision: RiskTierDecision) -> Dict[str, Any]:
    """
    Map Risk-Tier to retrieval / rerank / verification / HITL behaviour.
    This does not execute the behaviour; it emits a structured, auditable plan.
    """
    tier = decision.risk_tier

    # Retrieval matrix
    if tier == "R0":
        retrieval_plan = {"mode": "dense", "hybrid": False, "metadata_filter": False}
    elif tier == "R1":
        retrieval_plan = {"mode": "hybrid_light", "hybrid": True, "metadata_filter": False}
    elif tier == "R2":
        retrieval_plan = {"mode": "hybrid_full", "hybrid": True, "metadata_filter": False}
    elif tier == "R3":
        retrieval_plan = {"mode": "hybrid_full", "hybrid": True, "metadata_filter": True}
    else:  # R4
        retrieval_plan = {"mode": "blocked", "hybrid": False, "metadata_filter": False}

    # Rerank matrix
    if tier == "R0":
        rerank_plan = {"mode": "none"}
    elif tier == "R1":
        rerank_plan = {"mode": "rule"}
    elif tier == "R2":
        rerank_plan = {"mode": "rule+model"}
    elif tier == "R3":
        rerank_plan = {"mode": "rule+model+llm"}
    else:
        rerank_plan = {"mode": "blocked"}

    # Verification strength
    if tier == "R0":
        verification_plan = {"level": "basic"}
    elif tier == "R1":
        verification_plan = {"level": "claim"}
    elif tier == "R2":
        verification_plan = {"level": "claim+span"}
    elif tier == "R3":
        verification_plan = {"level": "claim+span+numeric"}
    else:
        verification_plan = {"level": "blocked"}

    # HITL rules
    hitl_policy: Dict[str, Any]
    if tier == "R3":
        hitl_policy = {
            "on_insufficient_evidence": "force_human",
            "on_verification_fail": "refuse_and_hitl",
        }
    elif tier == "R4":
        hitl_policy = {
            "on_entry": "refuse_and_hitl",
        }
    else:
        hitl_policy = {
            "on_verification_fail": "conservative_answer",
        }

    return {
        "risk_tier": decision.to_dict(),
        "retrieval_plan": retrieval_plan,
        "rerank_plan": rerank_plan,
        "verification_plan": verification_plan,
        "hitl_policy": hitl_policy,
    }





