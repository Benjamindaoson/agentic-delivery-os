"""
Online RAG pipeline skeleton with Risk-Tier as first-class control variable.

This module does NOT execute retrieval/generation yet. It:
- Determines Risk-Tier
- Builds retrieval / rerank / verification / HITL plans
- Emits an auditable trace-like dict that can be logged / stored.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .risk_tier import RiskTierDecision, determine_risk_tier, build_online_plans


def run_online_query(
    profile: str,
    query: str,
    language: str = "auto",
    index_version: str = "latest",
    mode: str = "auto",
    explicit_risk_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Minimal online pipeline entry for Phase 8 P2 tests.

    Returns a structured dict capturing:
    - risk_tier decision (tier/source/confidence)
    - retrieval / rerank / verification plans
    - hitl_policy
    - high-level response contract compatible with /api/query expectations.
    """
    rt_decision: RiskTierDecision = determine_risk_tier(
        profile=profile,
        query=query,
        explicit_tier=explicit_risk_tier,
    )
    plans = build_online_plans(rt_decision)
    tier = rt_decision.risk_tier

    # For now we don't call real retrieval/generation; we shape the response.
    if tier == "R4":
        answer = ""
        verification_result = {
            "passed": False,
            "reasons": ["R4_forced_refusal"],
            "risk_level": "high",
        }
        hitl_triggered = True
    else:
        # Stub answer; later this will be produced by the true generation pipeline.
        answer = "stub answer"
        verification_result = {
            "passed": True,
            "reasons": [],
            "risk_level": "low" if tier in ("R0", "R1") else "medium",
        }
        hitl_triggered = False

    return {
        "answer": answer,
        "citations": [],  # will be populated once retrieval/generation are wired
        "verification": verification_result,
        "trace": {
            "risk_tier": plans["risk_tier"],
            "retrieval_plan": plans["retrieval_plan"],
            "rerank_plan": plans["rerank_plan"],
            "verification_plan": plans["verification_plan"],
            "hitl_policy": plans["hitl_policy"],
            "hitl_triggered": hitl_triggered,
            "index_version": index_version,
            "mode": mode,
            "language": language,
        },
    }





