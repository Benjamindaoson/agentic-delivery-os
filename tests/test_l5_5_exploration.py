"""
L5.5 Exploration tests:
- Budget exhausted stops exploration
- Controlled exploration generates candidate + shadow diff
- Regression block rejects rollout
- Reward targets retrieval when attribution points to retrieval
- Artifacts auditability (schema_version present)
"""
import asyncio
import json
import os
from pathlib import Path

from runtime.exploration.exploration_engine import ExplorationEngine
from runtime.exploration.strategy_genome import StrategyGenome
from runtime.exploration.discovery_reward import compute_reward
from runtime.eval.policy_regression_runner import PolicyRegressionRunner
from runtime.shadow.shadow_executor import ShadowExecutor


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_budget_exhausted_stops_exploration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = ExplorationEngine(
        artifacts_dir=str(tmp_path / "artifacts"),
        max_failures=0,
        max_cost_usd=0.0,
    )
    run_signals = {
        "run_success": False,
        "pattern_is_new": True,
        "retrieval_policy_id": "basic_v1",
        "generation_template_id": "rag_answer:v1",
    }
    decision = run(
        engine.maybe_explore(
            run_id="run_budget_stop",
            run_signals=run_signals,
            attribution={"primary_cause": "RETRIEVAL_MISS"},
            policy_kpis={"success_rate": 0.5},
        )
    )
    assert decision["decision"]["explore"] is False
    assert decision["guards"]["hard_stop"] is True
    assert (tmp_path / "artifacts" / "exploration" / "decisions" / "run_budget_stop.json").exists()


def test_controlled_exploration_creates_candidate_and_shadow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = ExplorationEngine(
        artifacts_dir=str(tmp_path / "artifacts"),
        max_failures=5,
        max_cost_usd=10.0,
    )
    run_signals = {
        "run_success": False,
        "pattern_is_new": True,
        "retrieval_policy_id": "basic_v1",
        "generation_template_id": "rag_answer:v1",
        "pattern_hash": "tool_chain_x",
    }
    decision = run(
        engine.maybe_explore(
            run_id="run_explore",
            run_signals=run_signals,
            attribution={"primary_cause": "RETRIEVAL_MISS"},
            policy_kpis={"success_rate": 0.6},
        )
    )
    candidates_dir = tmp_path / "artifacts" / "policy" / "candidates"
    files = list(candidates_dir.glob("*.json"))
    assert files, "candidate artifact not generated"
    shadow_dir = tmp_path / "artifacts" / "shadow_diff"
    alt_shadow_dir = tmp_path / "artifacts" / "eval" / "shadow_diff"
    assert shadow_dir.exists() or alt_shadow_dir.exists()
    assert decision["decision"]["explore"] is True


def test_regression_block_rejects_candidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = PolicyRegressionRunner(
        artifacts_dir=str(tmp_path / "artifacts"),
        threshold_success_drop=0.1,
        threshold_cost_increase=0.1,
    )
    historical_runs = [{"q": i} for i in range(10)]
    golden = [{"expected_success": True, "expected_cost": 0.05} for _ in range(10)]

    async def bad_runner(payload):
        return {"success": False, "cost": 0.2, "latency_ms": 300, "error_type": "regression"}

    verdict = run(
        runner.run(
            candidate_policy_id="cand_bad",
            historical_runs=historical_runs,
            golden_results=golden,
            candidate_runner=bad_runner,
        )
    )
    assert verdict.pass_regression is False
    assert "success_rate_drop" in verdict.blocking_reasons
    report = tmp_path / "artifacts" / "eval" / "golden_replay_report_cand_bad.json"
    assert report.exists()


def test_reward_targets_retrieval(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = ExplorationEngine(artifacts_dir=str(tmp_path / "artifacts"))
    run_signals = {
        "run_success": False,
        "pattern_is_new": True,
        "retrieval_policy_id": "basic_v1",
    }
    decision = engine._decide(
        run_id="run_reward",
        run_signals=run_signals,
        attribution={"primary_cause": "RETRIEVAL_MISS"},
        policy_kpis={"success_rate": 0.6},
        feedback_events=None,
    )
    assert decision["decision"]["target_space"] == ["retrieval"]

    # reward computation uses retrieval attribution weight
    diff = {
        "decision_divergence": True,
        "success_delta": 0.2,
        "cost_delta": 0.0,
        "latency_delta": 0.0,
    }
    reward = compute_reward(
        shadow_diff=diff,
        golden_coverage_gain=0.1,
        attribution_weights={"retrieval": 0.9},
        evidence_usage_rate=0.5,
        cost_delta=0.0,
        latency_delta=0.0,
    )
    assert reward.reward_total > 0


def test_auditability_artifacts_have_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = ExplorationEngine(artifacts_dir=str(tmp_path / "artifacts"))
    run_signals = {
        "run_success": False,
        "pattern_is_new": True,
        "retrieval_policy_id": "basic_v1",
        "generation_template_id": "rag_answer:v1",
    }
    run(
        engine.maybe_explore(
            run_id="run_audit",
            run_signals=run_signals,
            attribution={"primary_cause": "RETRIEVAL_MISS"},
            policy_kpis={"success_rate": 0.6},
        )
    )
    decision_path = tmp_path / "artifacts" / "exploration" / "decisions" / "run_audit.json"
    assert decision_path.exists()
    data = json.loads(decision_path.read_text(encoding="utf-8"))
    assert "schema_version" in data
    # candidate artifact
    candidates = list((tmp_path / "artifacts" / "policy" / "candidates").glob("*.json"))
    assert candidates
    cand_data = json.loads(candidates[0].read_text(encoding="utf-8"))
    assert "schema_version" in cand_data



