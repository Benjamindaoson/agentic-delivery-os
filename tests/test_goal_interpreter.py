"""
Tests for Goal Interpreter.
Validates Goal → Reward determinism and goal artifact completeness.
"""
import os
import json
import pytest

from runtime.planning.goal_interpreter import (
    GoalInterpreter,
    Goal,
    GoalType,
    SuccessCriterion,
    Constraint,
    ConstraintType
)
from runtime.planning.reward_model import RewardModel, RewardSignal


class TestGoalInterpreter:
    """Goal interpretation tests."""
    
    def test_interpret_basic_question(self, tmp_path, monkeypatch):
        """Test interpreting a basic question."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret(
            run_id="test_run_001",
            task_input={"query": "What is the capital of France?"}
        )
        
        assert goal.goal_id is not None
        assert goal.run_id == "test_run_001"
        assert goal.goal_type == GoalType.ANSWER
        assert len(goal.success_criteria) > 0
        
        # Artifact should exist
        artifact_path = tmp_path / "artifacts" / "goals" / "test_run_001.json"
        assert artifact_path.exists()
    
    def test_goal_type_classification(self, tmp_path, monkeypatch):
        """Test goal type is correctly classified."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Answer type
        goal = interpreter.interpret("run_answer", {"query": "What is machine learning?"})
        assert goal.goal_type == GoalType.ANSWER
        
        # Transform type
        goal = interpreter.interpret("run_transform", {"query": "Convert this CSV to JSON"})
        assert goal.goal_type == GoalType.TRANSFORM
        
        # Decide type
        goal = interpreter.interpret("run_decide", {"query": "Should we use Python or Go?"})
        assert goal.goal_type == GoalType.DECIDE
        
        # Explore type
        goal = interpreter.interpret("run_explore", {"query": "Find all related papers"})
        assert goal.goal_type == GoalType.EXPLORE
    
    def test_goal_has_required_fields(self, tmp_path, monkeypatch):
        """Test goal artifact has all required fields."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret(
            run_id="test_fields",
            task_input={"query": "Test query", "max_cost": 1.0}
        )
        
        # Check all required fields
        goal_dict = goal.to_dict()
        
        required_fields = [
            "goal_id", "run_id", "goal_type", "description",
            "success_criteria", "constraints", "optimization_targets",
            "uncertainty_factors", "schema_version"
        ]
        
        for field in required_fields:
            assert field in goal_dict, f"Missing field: {field}"
    
    def test_goal_is_hashable(self, tmp_path, monkeypatch):
        """Test goal can be hashed for replay."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret("run_hash", {"query": "Test query"})
        
        hash1 = goal.to_hash()
        assert len(hash1) == 16
        
        # Same goal should produce same hash
        goal2 = interpreter.load_goal("run_hash")
        hash2 = goal2.to_hash()
        
        assert hash1 == hash2
    
    def test_constraints_extracted(self, tmp_path, monkeypatch):
        """Test constraints are extracted from input."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret(
            run_id="run_constraints",
            task_input={
                "query": "Answer this question",
                "max_cost": 0.5,
                "max_latency_ms": 3000,
                "min_quality": 0.8
            }
        )
        
        assert len(goal.constraints) >= 3
        
        # Check constraint types
        constraint_scopes = [c.scope for c in goal.constraints]
        assert "cost" in constraint_scopes
        assert "latency" in constraint_scopes
        assert "quality" in constraint_scopes


class TestRewardModel:
    """Reward model tests."""
    
    def test_compute_reward_success(self, tmp_path, monkeypatch):
        """Test reward computation for successful outcome."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret("run_reward_success", {"query": "What is 2+2?"})
        
        outcome = {
            "success": True,
            "output": "The answer is 4 because 2+2 equals 4.",
            "quality_score": 0.95
        }
        
        metrics = {
            "cost": 0.01,
            "latency_ms": 500,
            "retries": 0
        }
        
        reward = reward_model.compute_reward(goal, outcome, metrics)
        
        assert reward.sparse_reward == 1.0
        assert reward.dense_reward > 0.5
        assert reward.net_reward > 0
        
        # Artifact should exist
        artifact_path = tmp_path / "artifacts" / "rewards" / "run_reward_success.json"
        assert artifact_path.exists()
    
    def test_compute_reward_failure(self, tmp_path, monkeypatch):
        """Test reward computation for failed outcome."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret("run_reward_fail", {"query": "What is 2+2?"})
        
        outcome = {
            "success": False,
            "output": "I don't know",
            "quality_score": 0.2
        }
        
        metrics = {
            "cost": 0.05,
            "latency_ms": 2000,
            "retries": 3
        }
        
        reward = reward_model.compute_reward(goal, outcome, metrics)
        
        assert reward.sparse_reward == 0.0
        assert reward.total_penalty > 0
        assert reward.net_reward < reward.total_reward
    
    def test_reward_is_deterministic(self, tmp_path, monkeypatch):
        """Test same input produces same reward."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret("run_det", {"query": "Test query"})
        
        outcome = {"success": True, "output": "Answer is here."}
        metrics = {"cost": 0.02}
        
        reward1 = reward_model.compute_reward(goal, outcome, metrics)
        
        # Reload and recompute
        goal2 = interpreter.load_goal("run_det")
        reward2 = reward_model.compute_reward(goal2, outcome, metrics)
        
        assert reward1.sparse_reward == reward2.sparse_reward
        assert reward1.dense_reward == reward2.dense_reward
    
    def test_reward_has_components(self, tmp_path, monkeypatch):
        """Test reward has decomposed components."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        goal = interpreter.interpret("run_components", {"query": "Question?"})
        outcome = {"success": True, "output": "Answer here."}
        
        reward = reward_model.compute_reward(goal, outcome, {})
        
        assert len(reward.success_components) > 0
        assert len(reward.optimization_components) > 0
        
        # All components have required fields
        for comp in reward.success_components:
            assert comp.component_id is not None
            assert comp.source == "criterion"
            assert 0 <= comp.value <= 1


class TestGoalRewardIntegration:
    """Integration tests for Goal → Reward flow."""
    
    def test_full_goal_reward_flow(self, tmp_path, monkeypatch):
        """Test complete Goal → Reward flow."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Step 1: Interpret goal
        goal = interpreter.interpret(
            run_id="integration_test",
            task_input={
                "query": "What are the benefits of exercise?",
                "max_cost": 0.1,
                "max_latency_ms": 5000
            }
        )
        
        # Step 2: Simulate execution
        outcome = {
            "success": True,
            "output": "Exercise is beneficial because it improves cardiovascular health.",
            "quality_score": 0.85
        }
        
        metrics = {
            "cost": 0.03,
            "latency_ms": 1200,
            "retries": 0,
            "evidence_count": 3
        }
        
        # Step 3: Compute reward
        reward = reward_model.compute_reward(goal, outcome, metrics)
        
        # Verify flow
        assert goal.goal_id is not None
        assert reward.goal_id == goal.goal_id
        assert reward.run_id == goal.run_id
        
        # Both artifacts exist
        assert os.path.exists(str(tmp_path / "artifacts" / "goals" / "integration_test.json"))
        assert os.path.exists(str(tmp_path / "artifacts" / "rewards" / "integration_test.json"))
    
    def test_goal_reward_replayable(self, tmp_path, monkeypatch):
        """Test Goal → Reward is replayable from artifacts."""
        monkeypatch.chdir(tmp_path)
        
        interpreter = GoalInterpreter(artifacts_dir=str(tmp_path / "artifacts"))
        reward_model = RewardModel(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Create
        goal = interpreter.interpret("replay_test", {"query": "Test"})
        outcome = {"success": True, "output": "Result"}
        reward = reward_model.compute_reward(goal, outcome, {})
        
        # Reload
        loaded_goal = interpreter.load_goal("replay_test")
        loaded_reward = reward_model.load_reward("replay_test")
        
        assert loaded_goal.goal_id == goal.goal_id
        assert loaded_reward.net_reward == reward.net_reward



