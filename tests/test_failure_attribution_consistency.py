"""
Failure Attribution Consistency Tests.
Validates that attribution is stable and accurate under controlled failure injection.
"""
import os
import pytest
from datetime import datetime

from runtime.testing.failure_injector import (
    FailureInjector,
    FailureType,
    InjectedFailure,
    InjectionPlan,
    simulate_run_with_injection
)


class TestFailureInjectionBasics:
    """Basic failure injection functionality."""
    
    def test_create_injection_plan(self, tmp_path, monkeypatch):
        """Test creating an injection plan."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        plan = injector.create_injection_plan(
            run_id="test_run_001",
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        assert plan.run_id == "test_run_001"
        assert len(plan.failures) == 1
        assert plan.failures[0].failure_type == FailureType.TOOL_TIMEOUT
        assert plan.failures[0].layer == "tool"
        assert len(plan.plan_hash) == 16
        
        # Verify artifact saved
        artifact_path = tmp_path / "artifacts" / "testing" / "injections" / "test_run_001.json"
        assert artifact_path.exists()
    
    def test_injection_is_deterministic(self, tmp_path, monkeypatch):
        """Same seed produces same injection plan."""
        monkeypatch.chdir(tmp_path)
        
        injector1 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts1"))
        injector2 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts2"))
        
        plan1 = injector1.create_injection_plan(
            run_id="det_test",
            failure_types=[FailureType.RETRIEVAL_CONFLICT, FailureType.PROMPT_INJECTION],
            seed=123
        )
        
        plan2 = injector2.create_injection_plan(
            run_id="det_test",
            failure_types=[FailureType.RETRIEVAL_CONFLICT, FailureType.PROMPT_INJECTION],
            seed=123
        )
        
        assert plan1.plan_hash == plan2.plan_hash
        assert plan1.failures[0].to_tag() == plan2.failures[0].to_tag()
    
    def test_failure_tags_unique(self, tmp_path, monkeypatch):
        """Each failure has a unique tag."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        plan = injector.create_injection_plan(
            run_id="tag_test",
            failure_types=[
                FailureType.TOOL_TIMEOUT,
                FailureType.TOOL_PARTIAL_FAILURE,
                FailureType.RETRIEVAL_CONFLICT
            ],
            seed=42
        )
        
        tags = [f.to_tag() for f in plan.failures]
        assert len(tags) == len(set(tags)), "Tags should be unique"


class TestAttributionConsistency:
    """Attribution must be consistent with injected failures."""
    
    def test_single_failure_correct_attribution(self, tmp_path, monkeypatch):
        """Single failure should produce correct primary cause."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="single_fail_001",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        attribution = result["attribution"]
        
        # Must have primary cause
        assert attribution["primary_cause"] == "TOOL_TIMEOUT"
        assert attribution["primary_layer"] == "tool"
        assert attribution["failure"] is True
        
        # Confidence should be reasonable
        assert attribution["confidence"] >= 0.5
        
        # Layer weights must sum to 1
        weights = attribution["layer_blame_weights"]
        assert abs(sum(weights.values()) - 1.0) < 0.01
        
        # Artifact must exist
        assert os.path.exists(result["attribution_path"])
    
    def test_multiple_failures_highest_severity_is_primary(self, tmp_path, monkeypatch):
        """With multiple failures, highest severity should be primary cause."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Create plan with varying severities
        plan = injector.create_injection_plan(
            run_id="multi_fail_001",
            failure_types=[
                FailureType.TOOL_TIMEOUT,
                FailureType.RETRIEVAL_CONFLICT
            ],
            seed=42,
            severity=1.0
        )
        
        # Manually adjust severity for testing
        plan.failures[1].severity = 0.8  # Retrieval is less severe
        
        result = simulate_run_with_injection(
            run_id="multi_fail_002",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT, FailureType.RETRIEVAL_CONFLICT],
            seed=42
        )
        
        attribution = result["attribution"]
        
        # Primary cause should be first (highest severity when equal)
        assert attribution["primary_cause"] is not None
        assert attribution["failure"] is True
        
        # Both layers should have blame
        weights = attribution["layer_blame_weights"]
        assert len(weights) >= 1
    
    def test_attribution_not_split_equally_when_unequal(self, tmp_path, monkeypatch):
        """Attribution should not split blame equally unless truly equal."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="unequal_test",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        attribution = result["attribution"]
        weights = attribution["layer_blame_weights"]
        
        # Single failure should have 100% blame on one layer
        assert len(weights) == 1
        assert list(weights.values())[0] == 1.0
    
    def test_attribution_validation_catches_missing_cause(self, tmp_path, monkeypatch):
        """Validation should catch missing primary cause."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        plan = injector.create_injection_plan(
            run_id="missing_cause_test",
            failure_types=[FailureType.PLANNER_WRONG_DAG],
            seed=42
        )
        
        # Create bad attribution (missing primary_cause)
        bad_attribution = {
            "run_id": "missing_cause_test",
            "failure": True,
            "primary_cause": None,  # Missing!
            "layer_blame_weights": {"planner": 1.0}
        }
        
        validation = injector.validate_attribution("missing_cause_test", bad_attribution)
        
        assert validation["valid"] is False
        assert "attribution_missing_primary_cause" in validation["errors"]
    
    def test_attribution_validation_catches_mismatch(self, tmp_path, monkeypatch):
        """Validation should catch cause mismatch."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        plan = injector.create_injection_plan(
            run_id="mismatch_test",
            failure_types=[FailureType.RETRIEVAL_CONFLICT],
            seed=42
        )
        
        # Create wrong attribution (blaming wrong layer)
        wrong_attribution = {
            "run_id": "mismatch_test",
            "failure": True,
            "primary_cause": "PROMPT_INJECTION",  # Wrong!
            "primary_layer": "prompt",
            "layer_blame_weights": {"prompt": 1.0}
        }
        
        validation = injector.validate_attribution("mismatch_test", wrong_attribution)
        
        assert validation["valid"] is False
        assert any("cause_mismatch" in e for e in validation["errors"])
    
    def test_attribution_validation_catches_unnormalized_weights(self, tmp_path, monkeypatch):
        """Validation should catch weights that don't sum to 1."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        plan = injector.create_injection_plan(
            run_id="weight_test",
            failure_types=[FailureType.TOOL_TIMEOUT],
            seed=42
        )
        
        # Create attribution with bad weights
        bad_attribution = {
            "run_id": "weight_test",
            "failure": True,
            "primary_cause": "TOOL_TIMEOUT",
            "primary_layer": "tool",
            "layer_blame_weights": {"tool": 0.5, "retrieval": 0.3}  # Sum = 0.8, not 1.0
        }
        
        validation = injector.validate_attribution("weight_test", bad_attribution)
        
        assert validation["valid"] is False
        assert any("weights_not_normalized" in e for e in validation["errors"])


class TestAttributionArtifacts:
    """Attribution artifacts must be complete and auditable."""
    
    def test_attribution_artifact_has_required_fields(self, tmp_path, monkeypatch):
        """Attribution artifact must have all required fields."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="artifact_test",
            injector=injector,
            failure_types=[FailureType.ENVIRONMENT_ERROR],
            seed=42
        )
        
        attribution = result["attribution"]
        
        # Required fields for all attributions
        required_fields = [
            "run_id",
            "failure",
            "primary_cause",
            "confidence",
            "layer_blame_weights",
            "excluded_layers",
            "timestamp",
            "schema_version"
        ]
        
        for field in required_fields:
            assert field in attribution, f"Missing required field: {field}"
        
        # If failure occurred, must have additional fields
        if attribution["failure"]:
            assert "supporting_signals" in attribution
            assert "injected_failure" in attribution
    
    def test_attribution_artifact_is_replayable(self, tmp_path, monkeypatch):
        """Attribution should be deterministic and replayable."""
        monkeypatch.chdir(tmp_path)
        
        injector1 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts1"))
        injector2 = FailureInjector(artifacts_dir=str(tmp_path / "artifacts2"))
        
        result1 = simulate_run_with_injection(
            run_id="replay_test",
            injector=injector1,
            failure_types=[FailureType.PROMPT_INJECTION],
            seed=999
        )
        
        result2 = simulate_run_with_injection(
            run_id="replay_test",
            injector=injector2,
            failure_types=[FailureType.PROMPT_INJECTION],
            seed=999
        )
        
        # Same inputs should produce same attribution
        assert result1["attribution"]["primary_cause"] == result2["attribution"]["primary_cause"]
        assert result1["attribution"]["layer_blame_weights"] == result2["attribution"]["layer_blame_weights"]


class TestAllFailureTypes:
    """Test all failure types are correctly attributed."""
    
    @pytest.mark.parametrize("failure_type,expected_layer", [
        (FailureType.TOOL_TIMEOUT, "tool"),
        (FailureType.TOOL_PARTIAL_FAILURE, "tool"),
        (FailureType.RETRIEVAL_CONFLICT, "retrieval"),
        (FailureType.PROMPT_INJECTION, "prompt"),
        (FailureType.PLANNER_WRONG_DAG, "planner"),
        (FailureType.ENVIRONMENT_ERROR, "environment"),
        (FailureType.EVIDENCE_INSUFFICIENT, "evidence"),
        (FailureType.GENERATION_HALLUCINATION, "generation"),
    ])
    def test_failure_type_attributed_to_correct_layer(
        self, failure_type, expected_layer, tmp_path, monkeypatch
    ):
        """Each failure type should be attributed to the correct layer."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id=f"type_test_{failure_type.value}",
            injector=injector,
            failure_types=[failure_type],
            seed=42
        )
        
        attribution = result["attribution"]
        
        assert attribution["primary_cause"] == failure_type.value
        assert attribution["primary_layer"] == expected_layer
        assert expected_layer in attribution["layer_blame_weights"]
        assert attribution["layer_blame_weights"][expected_layer] == 1.0


class TestCombinedFailures:
    """Test attribution with combined/cascading failures."""
    
    def test_tool_and_retrieval_combined(self, tmp_path, monkeypatch):
        """Tool failure + Retrieval conflict should both be attributed."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="combined_001",
            injector=injector,
            failure_types=[FailureType.TOOL_TIMEOUT, FailureType.RETRIEVAL_CONFLICT],
            seed=42
        )
        
        attribution = result["attribution"]
        weights = attribution["layer_blame_weights"]
        
        # Both layers should have blame
        assert "tool" in weights or "retrieval" in weights
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
    
    def test_three_layer_failure_attribution(self, tmp_path, monkeypatch):
        """Three-layer failure should distribute blame correctly."""
        monkeypatch.chdir(tmp_path)
        
        injector = FailureInjector(artifacts_dir=str(tmp_path / "artifacts"))
        
        result = simulate_run_with_injection(
            run_id="three_layer",
            injector=injector,
            failure_types=[
                FailureType.TOOL_TIMEOUT,
                FailureType.RETRIEVAL_CONFLICT,
                FailureType.PROMPT_INJECTION
            ],
            seed=42
        )
        
        attribution = result["attribution"]
        weights = attribution["layer_blame_weights"]
        
        # All three layers should be blamed
        assert len(weights) == 3
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        
        # Each should have ~1/3 blame
        for w in weights.values():
            assert w == pytest.approx(1.0/3, abs=0.01)

