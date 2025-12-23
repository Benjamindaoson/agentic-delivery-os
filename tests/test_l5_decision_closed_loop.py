"""
L5 decision-closed-loop tests:
- attribution correctness
- shadow vs active diff
- regression block
- feedback ingestion
- strategy selector convergence
"""
import asyncio
import os
import json
from datetime import datetime

from runtime.analysis.decision_attributor import DecisionAttributor
from runtime.shadow.shadow_executor import ShadowExecutor
from runtime.eval.policy_regression_runner import PolicyRegressionRunner
from runtime.feedback.feedback_collector import FeedbackCollector
from runtime.strategy.strategy_selector import StrategySelector


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def run(coro):
    """Helper to run async coroutine in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_decision_attribution_primary_cause(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    attributor = DecisionAttributor(artifacts_dir=str(tmp_path / "artifacts"))

    run_signals = {
        "run_success": False,
        "tool_failure_types": {"TIMEOUT": 2, "INVALID_INPUT": 1},
        "tool_success_rate": 0.4,
        "retrieval_num_docs": 10,
        "evidence_usage_rate": 0.6,
        "retrieval_policy_historical_success_rate": 0.9,
    }

    result = run(
        attributor.attribute(
            run_id="run_attribution_1",
            run_signals=run_signals,
            planner_decision={"mode": "normal"},
        )
    )

    assert result.failure is True
    assert result.primary_cause == "TOOL_TIMEOUT"
    assert result.confidence > 0.5
    # artifact exists
    assert (tmp_path / "artifacts" / "attributions" / "run_attribution_1.json").exists()


def test_shadow_executor_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executor = ShadowExecutor(artifacts_dir=str(tmp_path / "artifacts"))

    async def active_runner(payload):
        return {
            "decision": "use_v1",
            "success": True,
            "cost": 0.1,
            "latency_ms": 200,
        }

    async def candidate_runner(payload):
        return {
            "decision": "use_v2",
            "success": True,
            "cost": 0.08,
            "latency_ms": 180,
        }

    result = run(
        executor.run_shadow(
            run_id="shadow_1",
            input_payload={"query": "hello"},
            active_runner=active_runner,
            candidate_runner=candidate_runner,
        )
    )

    assert result.decision_divergence is True
    assert abs(result.cost_delta + 0.02) < 1e-6
    assert abs(result.latency_delta + 20) < 1e-6
    assert (tmp_path / "artifacts" / "shadow_diff" / "shadow_1.json").exists()


def test_policy_regression_runner_blocks_on_drop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = PolicyRegressionRunner(
        artifacts_dir=str(tmp_path / "artifacts"),
        threshold_success_drop=0.05,
        threshold_cost_increase=0.1,
    )

    historical_runs = [{"input": i} for i in range(10)]
    golden_results = [{"expected_success": True, "expected_cost": 0.1} for _ in range(10)]

    async def candidate_runner(payload):
        # introduce regressions: only 60% success, higher cost
        success = payload["input"] % 5 != 0
        return {
            "success": success,
            "cost": 0.15,
            "latency_ms": 120,
            "error_type": "timeout" if not success else None,
        }

    verdict = run(
        runner.run(
            candidate_policy_id="policy_candidate_v2",
            historical_runs=historical_runs,
            golden_results=golden_results,
            candidate_runner=candidate_runner,
        )
    )

    assert verdict.pass_regression is False
    assert verdict.safe_to_rollout is False
    assert "success_rate_drop" in verdict.blocking_reasons
    assert (tmp_path / "artifacts" / "policy_regression_report.json").exists()


def test_feedback_collector_ingestion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    collector = FeedbackCollector(artifacts_dir=str(tmp_path / "artifacts"))

    run(
        collector.record(
            run_id="run_fb_1",
            feedback_type="user_accept",
            payload={"note": "looks good"},
        )
    )
    run(
        collector.record(
            run_id="run_fb_1",
            feedback_type="user_edit",
            payload={"edit": "fixed typo"},
        )
    )

    events = collector.list_events()
    assert len(events) == 2
    assert events[0]["feedback_type"] == "user_accept"
    assert events[1]["feedback_type"] == "user_edit"
    assert (tmp_path / "artifacts" / "feedback_events.json").exists()


def test_strategy_selector_convergence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    selector = StrategySelector(artifacts_dir=str(tmp_path / "artifacts"), epsilon=0.0, seed=7)

    # First choose to initialize arms
    first = run(selector.choose("retrieval", ["r_v1", "r_v2"], context={"task": "qa"}))
    assert first.chosen_arm in {"r_v1", "r_v2"}

    # Update rewards: r_v2 is better
    run(selector.update_reward("retrieval", "r_v1", reward=0.1))
    run(selector.update_reward("retrieval", "r_v2", reward=0.9))

    # Next choose should exploit best average reward (r_v2)
    second = run(selector.choose("retrieval", ["r_v1", "r_v2"], context={"task": "qa"}))
    assert second.chosen_arm == "r_v2"

    # Decisions file exists
    assert (tmp_path / "artifacts" / "strategy_decisions.json").exists()

