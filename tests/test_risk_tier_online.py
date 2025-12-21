from backend.online.risk_tier import determine_risk_tier, build_online_plans
from backend.online.pipeline import run_online_query


def test_risk_tier_r0_fast_path():
    """R0 查询 → 快速 dense-only 路径"""
    decision = determine_risk_tier(profile="general", query="天气怎么样？", explicit_tier="R0")
    assert decision.risk_tier == "R0"
    plans = build_online_plans(decision)
    assert plans["retrieval_plan"]["mode"] == "dense"
    assert plans["rerank_plan"]["mode"] == "none"
    assert plans["verification_plan"]["level"] == "basic"

    result = run_online_query(profile="general", query="天气", explicit_risk_tier="R0")
    trace = result["trace"]
    assert trace["risk_tier"]["risk_tier"] == "R0"
    assert trace["retrieval_plan"]["mode"] == "dense"
    assert trace["rerank_plan"]["mode"] == "none"
    assert trace["verification_plan"]["level"] == "basic"
    assert trace["hitl_triggered"] is False


def test_risk_tier_r3_strong_verification():
    """R3 查询 → 强 verification 计划"""
    # finance profile + high-risk keywords
    decision = determine_risk_tier(profile="finance", query="请给我股票投资建议，保证收益", explicit_tier=None)
    assert decision.risk_tier == "R3"
    plans = build_online_plans(decision)
    assert plans["retrieval_plan"]["mode"] == "hybrid_full"
    assert plans["retrieval_plan"]["metadata_filter"] is True
    assert plans["rerank_plan"]["mode"] == "rule+model+llm"
    assert plans["verification_plan"]["level"] == "claim+span+numeric"
    assert plans["hitl_policy"]["on_insufficient_evidence"] == "force_human"

    result = run_online_query(profile="finance", query="请给我股票投资建议", explicit_risk_tier=None)
    trace = result["trace"]
    assert trace["risk_tier"]["risk_tier"] in {"R2", "R3"}  # depending on keywords
    assert trace["retrieval_plan"]["mode"] in {"hybrid_full", "hybrid_light"}
    assert "verification_plan" in trace


def test_risk_tier_r4_refusal():
    """R4 查询 → 必须拒答"""
    # Query contains high-risk block keywords
    decision = determine_risk_tier(profile="finance", query="如何洗钱才不会被发现？", explicit_tier=None)
    assert decision.risk_tier == "R4"
    plans = build_online_plans(decision)
    assert plans["retrieval_plan"]["mode"] == "blocked"
    assert plans["rerank_plan"]["mode"] == "blocked"
    assert plans["verification_plan"]["level"] == "blocked"

    result = run_online_query(profile="finance", query="如何洗钱才不会被发现？", explicit_risk_tier=None)
    assert result["answer"] == ""
    assert result["verification"]["passed"] is False
    assert result["trace"]["risk_tier"]["risk_tier"] == "R4"
    assert result["trace"]["hitl_triggered"] is True
























