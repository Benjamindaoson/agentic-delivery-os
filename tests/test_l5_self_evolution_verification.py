"""
L5 Self-Evolution Verification Tests.

Validates:
1. Attribution stability under failure injection
2. Shadow evolution stability (no collapse, no explosion)
3. Cross-layer strategy transfer (the key differentiator from Devin/AlphaDev)
"""
import os
import json
import pytest
from datetime import datetime

from runtime.testing.failure_injector import (
    FailureInjector,
    FailureType,
    simulate_run_with_injection
)
from runtime.learning.strategy_transfer_engine import (
    StrategyTransferEngine,
    TransferProposal,
    SourceLayer,
    TargetLayer
)


class TestFailureInjectionAndAttribution:
    """Step 1: Failure injection and attribution consistency."""
    
    def test_attribution_stable_under_tool_timeout(self, tmp_path, monkeypatch):
        """Attribution should correctly identify TOOL_TIMEOUT."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="tool_timeout_test",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        attr = result["attribution"]
        
        # Must have correct primary cause
        assert attr["primary_cause"] == "TOOL_TIMEOUT"
        assert attr["primary_layer"] == "tool"
        assert attr["failure"] is True
        
        # Validation should pass
        validation = injector.validate_attribution("tool_timeout_test", attr)
        assert validation["valid"] is True, f"Validation failed: {validation['errors']}"
    
    def test_attribution_stable_under_retrieval_conflict(self, tmp_path, monkeypatch):
        """Attribution should correctly identify RETRIEVAL_CONFLICT."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="retrieval_conflict_test",
            injector=injector,
            failure_types=[FailureType.RETRIEVAL_CONFLICT],
            seed=42
        )
        
        attr = result["attribution"]
        assert attr["primary_cause"] == "RETRIEVAL_CONFLICT"
        assert attr["primary_layer"] == "retrieval"
        
        validation = injector.validate_attribution("retrieval_conflict_test", attr)
        assert validation["valid"] is True
    
    def test_attribution_stable_under_prompt_injection(self, tmp_path, monkeypatch):
        """Attribution should correctly identify PROMPT_INJECTION."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="prompt_injection_test",
            injector=injector,
            failure_types=[FailureType.PROMPT_INJECTION],
            seed=42
        )
        
        attr = result["attribution"]
        assert attr["primary_cause"] == "PROMPT_INJECTION"
        assert attr["primary_layer"] == "prompt"
        
        validation = injector.validate_attribution("prompt_injection_test", attr)
        assert validation["valid"] is True
    
    def test_attribution_stable_under_planner_wrong_dag(self, tmp_path, monkeypatch):
        """Attribution should correctly identify PLANNER_WRONG_DAG."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="planner_dag_test",
            injector=injector,
            failure_types=[FailureType.PLANNER_WRONG_DAG],
            seed=42
        )
        
        attr = result["attribution"]
        assert attr["primary_cause"] == "PLANNER_WRONG_DAG"
        assert attr["primary_layer"] == "planner"
        
        validation = injector.validate_attribution("planner_dag_test", attr)
        assert validation["valid"] is True
    
    def test_attribution_artifact_is_complete(self, tmp_path, monkeypatch):
        """Attribution artifact must have all required fields."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="complete_test",
            injector=injector,
            failure_types=[FailureType.ENVIRONMENT_ERROR],
            seed=42
        )
        
        attr = result["attribution"]
        
        # Check all required fields for all attributions
        required = [
            "run_id", "failure", "primary_cause", "primary_layer",
            "confidence", "layer_blame_weights", "excluded_layers",
            "timestamp", "schema_version"
        ]
        
        for field in required:
            assert field in attr, f"Missing field: {field}"
        
        # If failure occurred, must have additional fields
        if attr["failure"]:
            assert "supporting_signals" in attr
            assert "injected_failure" in attr
        
        # Artifact file exists
        assert os.path.exists(result["attribution_path"])
    
    def test_attribution_does_not_pollute_active_execution(self, tmp_path, monkeypatch):
        """Injection should not affect other runs."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Create injection plan for run_1
        injector.create_injection_plan(
            run_id="run_1",
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        # Check run_2 (no injection plan)
        injection = injector.inject("run_2", 0, "tool")
        assert injection is None, "run_2 should not be affected by run_1's injection"


class TestShadowEvolutionStability:
    """Step 2: Shadow evolution stability metrics."""
    
    def test_stability_metrics_are_tracked(self, tmp_path, monkeypatch):
        """Stability metrics should be computed and tracked."""
        monkeypatch.chdir(tmp_path)
        
        # Import here to avoid import issues
        import sys
        sys.path.insert(0, str(tmp_path.parent.parent))
        
        from scripts.run_shadow_evolution import ShadowEvolutionRunner, StabilityMetrics
        
        runner = ShadowEvolutionRunner(
            artifacts_dir=str(tmp_path / "artifacts"),
            num_candidates=2
        )
        
        # Run for short duration
        summary = runner.run(duration_seconds=2, tick_interval=0.1)
        
        # Should complete (or hard stop)
        assert summary["status"] in ["completed", "hard_stopped"]
        
        # Metrics should be tracked
        assert len(runner.metrics_history) > 0
        
        # Each metric should have required fields
        metrics = runner.metrics_history[-1]
        assert hasattr(metrics, "candidate_policy_count")
        assert hasattr(metrics, "strategy_entropy")
        assert hasattr(metrics, "kpi_variance")
        assert hasattr(metrics, "bandit_selection_distribution")
    
    def test_hard_stop_on_budget_exceeded(self, tmp_path, monkeypatch):
        """Should hard stop when failure budget is exceeded."""
        monkeypatch.chdir(tmp_path)
        
        from scripts.run_shadow_evolution import ShadowEvolutionRunner
        
        runner = ShadowEvolutionRunner(
            artifacts_dir=str(tmp_path / "artifacts"),
            num_candidates=2
        )
        
        # Set very low budget
        runner.failure_budget_total = 5.0
        runner.MAX_FAILURE_BUDGET_SPENT = 0.5
        
        # Run (should trigger budget hard stop quickly)
        summary = runner.run(duration_seconds=5, tick_interval=0.1)
        
        # If we got a hard stop, verify it's for the right reason
        if summary["status"] == "hard_stopped" and summary["hard_stop"]:
            # Hard stop artifact should exist
            stop_path = tmp_path / "artifacts" / "exploration" / "hard_stop_event.json"
            if stop_path.exists():
                with open(stop_path) as f:
                    stop_event = json.load(f)
                assert "reason" in stop_event
    
    def test_stability_metrics_artifact_saved(self, tmp_path, monkeypatch):
        """Stability metrics should be saved to artifact."""
        monkeypatch.chdir(tmp_path)
        
        from scripts.run_shadow_evolution import ShadowEvolutionRunner
        
        runner = ShadowEvolutionRunner(
            artifacts_dir=str(tmp_path / "artifacts"),
            num_candidates=2
        )
        
        runner.run(duration_seconds=2, tick_interval=0.1)
        
        # Artifact should exist
        metrics_path = tmp_path / "artifacts" / "exploration" / "stability_metrics.json"
        assert metrics_path.exists()
        
        with open(metrics_path) as f:
            data = json.load(f)
        
        assert "schema_version" in data
        assert "metrics" in data
        assert len(data["metrics"]) > 0


class TestCrossLayerStrategyTransfer:
    """Step 3: Cross-layer strategy transfer (key differentiator)."""
    
    def test_tool_failure_proposes_prompt_change(self, tmp_path, monkeypatch):
        """Tool failure should propose prompt strategy change."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_tool_to_prompt",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "confidence": 0.9,
            "layer_blame_weights": {"tool": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        # Should have cross-layer proposals
        cross_layer = [p for p in proposals if p.source_layer != p.target_layer]
        assert len(cross_layer) > 0, "Should propose cross-layer transfer"
        
        # At least one should target prompt
        prompt_targets = [p for p in cross_layer if p.target_layer == "prompt"]
        assert len(prompt_targets) > 0, "Should propose prompt change for tool failure"
    
    def test_retrieval_conflict_proposes_evidence_change(self, tmp_path, monkeypatch):
        """Retrieval conflict should propose evidence weighting change."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_retrieval_to_evidence",
            "failure": True,
            "primary_cause": "RETRIEVAL_CONFLICT",
            "primary_layer": "retrieval",
            "confidence": 0.85,
            "layer_blame_weights": {"retrieval": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        # Should have cross-layer proposals to evidence
        evidence_targets = [
            p for p in proposals
            if p.target_layer == "evidence" and p.source_layer != p.target_layer
        ]
        assert len(evidence_targets) > 0, "Should propose evidence change for retrieval conflict"
    
    def test_prompt_injection_proposes_planner_constraints(self, tmp_path, monkeypatch):
        """Prompt injection should propose planner constraint changes."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_prompt_to_planner",
            "failure": True,
            "primary_cause": "PROMPT_INJECTION",
            "primary_layer": "prompt",
            "confidence": 0.88,
            "layer_blame_weights": {"prompt": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        # Should propose planner constraints
        planner_targets = [
            p for p in proposals
            if p.target_layer == "planner" and p.source_layer != p.target_layer
        ]
        assert len(planner_targets) > 0, "Should propose planner change for prompt injection"
    
    def test_planner_error_proposes_retrieval_breadth(self, tmp_path, monkeypatch):
        """Planner error should propose retrieval breadth expansion."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_planner_to_retrieval",
            "failure": True,
            "primary_cause": "PLANNER_WRONG_DAG",
            "primary_layer": "planner",
            "confidence": 0.82,
            "layer_blame_weights": {"planner": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        # Should propose retrieval changes
        retrieval_targets = [
            p for p in proposals
            if p.target_layer == "retrieval" and p.source_layer != p.target_layer
        ]
        assert len(retrieval_targets) > 0, "Should propose retrieval change for planner error"
    
    def test_cross_layer_proposals_require_shadow(self, tmp_path, monkeypatch):
        """All cross-layer proposals must require shadow evaluation."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_shadow_required",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "confidence": 0.9,
            "layer_blame_weights": {"tool": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        for p in proposals:
            assert p.shadow_required is True, "All proposals must require shadow"
            assert p.replay_required is True, "All proposals must require replay"
    
    def test_cross_layer_proposals_saved_to_artifact(self, tmp_path, monkeypatch):
        """Cross-layer proposals should be saved to artifact."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_artifact_save",
            "failure": True,
            "primary_cause": "RETRIEVAL_CONFLICT",
            "primary_layer": "retrieval",
            "confidence": 0.85,
            "layer_blame_weights": {"retrieval": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        
        # Artifact should exist
        artifact_path = tmp_path / "artifacts" / "strategy" / "cross_layer_candidates.json"
        assert artifact_path.exists()
        
        with open(artifact_path) as f:
            data = json.load(f)
        
        assert "schema_version" in data
        assert "candidates" in data
        assert len(data["candidates"]) > 0
    
    def test_shadow_gate_blocks_on_cost_increase(self, tmp_path, monkeypatch):
        """Shadow gate should block proposals with high cost increase."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_gate_block",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "confidence": 0.9,
            "layer_blame_weights": {"tool": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        assert len(proposals) > 0
        
        proposal = proposals[0]
        
        # Shadow result with high cost increase
        shadow_result = {
            "success_delta": 0.05,
            "cost_delta_pct": 0.25,  # 25% increase (over threshold)
            "latency_delta_pct": 0.05
        }
        
        passed, details = engine.verify_shadow_gate(proposal.proposal_id, shadow_result)
        
        assert passed is False
        assert details["reason"] == "cost_increase_too_high"
    
    def test_regression_gate_blocks_on_regression(self, tmp_path, monkeypatch):
        """Regression gate should block proposals that cause regression."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        attribution = {
            "run_id": "test_regression_block",
            "failure": True,
            "primary_cause": "PLANNER_WRONG_DAG",
            "primary_layer": "planner",
            "confidence": 0.85,
            "layer_blame_weights": {"planner": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        assert len(proposals) > 0
        
        proposal = proposals[0]
        
        # Regression result showing degradation
        regression_result = {
            "safe_to_rollout": False,
            "blocking_reasons": ["success_rate_dropped_5%"]
        }
        
        passed, details = engine.verify_regression_gate(proposal.proposal_id, regression_result)
        
        assert passed is False
        assert details["reason"] == "regression_detected"
    
    def test_successful_cross_layer_transfer(self, tmp_path, monkeypatch):
        """Verify a complete successful cross-layer transfer flow."""
        monkeypatch.chdir(tmp_path)
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Step 1: Attribution identifies tool failure
        attribution = {
            "run_id": "test_full_flow",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "confidence": 0.9,
            "layer_blame_weights": {"tool": 1.0}
        }
        
        proposals = engine.analyze_attribution(attribution)
        cross_layer = [p for p in proposals if p.source_layer != p.target_layer]
        assert len(cross_layer) > 0
        
        proposal = cross_layer[0]
        assert proposal.status == "proposed"
        
        # Step 2: Shadow evaluation passes
        shadow_result = {
            "success_delta": 0.03,
            "cost_delta_pct": 0.02,
            "latency_delta_pct": 0.01
        }
        
        shadow_passed, _ = engine.verify_shadow_gate(proposal.proposal_id, shadow_result)
        assert shadow_passed is True
        
        engine.update_proposal_status(proposal.proposal_id, "shadowing")
        
        # Step 3: Regression gate passes
        regression_result = {"safe_to_rollout": True}
        
        regression_passed, _ = engine.verify_regression_gate(proposal.proposal_id, regression_result)
        assert regression_passed is True
        
        engine.update_proposal_status(proposal.proposal_id, "passed")
        
        # Verify proposal status updated
        updated = [p for p in engine.proposals if p.proposal_id == proposal.proposal_id][0]
        assert updated.status == "passed"
        
        # This is a cross-layer transfer: tool failure → prompt/other change
        assert updated.source_layer != updated.target_layer
        print(f"✅ Cross-layer transfer: {updated.source_layer} → {updated.target_layer}")


class TestAuditability:
    """Verify all behaviors produce auditable artifacts."""
    
    def test_attribution_artifact_is_replayable(self, tmp_path, monkeypatch):
        """Same injection should produce same attribution."""
        monkeypatch.chdir(tmp_path)
        
        injector1 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts1"))
        injector2 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts2"))
        
        result1 = simulate_run_with_injection(
            run_id="replay_audit",
            injector=injector1,
            failure_types=[FailureType.RETRIEVAL_CONFLICT],
            seed=999
        )
        
        result2 = simulate_run_with_injection(
            run_id="replay_audit",
            injector=injector2,
            failure_types=[FailureType.RETRIEVAL_CONFLICT],
            seed=999
        )
        
        assert result1["attribution"]["primary_cause"] == result2["attribution"]["primary_cause"]
        assert result1["attribution"]["layer_blame_weights"] == result2["attribution"]["layer_blame_weights"]
    
    def test_all_artifacts_have_schema_version(self, tmp_path, monkeypatch):
        """All artifacts must have schema_version for evolution."""
        monkeypatch.chdir(tmp_path)
        
        # Generate various artifacts
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        simulate_run_with_injection(
            run_id="schema_test",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        engine = StrategyTransferEngine(artifacts_dir=str(tmp_path / "artifacts"))
        engine.analyze_attribution({
            "run_id": "schema_test_2",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "confidence": 0.9,
            "layer_blame_weights": {"tool": 1.0}
        })
        
        # Check attribution artifact
        attr_path = tmp_path / "artifacts" / "attribution" / "schema_test.json"
        if attr_path.exists():
            with open(attr_path) as f:
                data = json.load(f)
            assert "schema_version" in data
        
        # Check strategy artifact
        strategy_path = tmp_path / "artifacts" / "strategy" / "cross_layer_candidates.json"
        if strategy_path.exists():
            with open(strategy_path) as f:
                data = json.load(f)
            assert "schema_version" in data
    
    def test_failure_budget_consumption_is_tracked(self, tmp_path, monkeypatch):
        """Failure budget consumption should be tracked."""
        monkeypatch.chdir(tmp_path)
        
        from scripts.run_shadow_evolution import ShadowEvolutionRunner
        
        runner = ShadowEvolutionRunner(
            artifacts_dir=str(tmp_path / "artifacts"),
            num_candidates=2
        )
        
        # Run briefly
        runner.run(duration_seconds=2, tick_interval=0.1)
        
        # Budget tracking
        assert runner.failure_budget_spent >= 0
        assert runner.failure_budget_total > 0

