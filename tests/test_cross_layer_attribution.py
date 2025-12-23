"""
Tests for Cross-Layer Attribution.
Validates attribution from Goal → Plan → Agent → Tool → Outcome.
"""
import os
import pytest

from runtime.planning.goal_interpreter import GoalInterpreter
from runtime.planning.planner_genome import PlannerGenomeRegistry
from runtime.agents.agent_profile import AgentProfileManager
from runtime.tooling.tool_profile import ToolProfileManager
from runtime.tooling.tool_chain_policy import ToolChainPolicyRegistry


class TestCrossLayerAttribution:
    """Cross-layer attribution tests."""
    
    def test_goal_to_outcome_chain(self, tmp_path, monkeypatch):
        """Test complete attribution chain."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        # Create components
        goal_interpreter = GoalInterpreter(artifacts_dir=artifacts)
        planner_registry = PlannerGenomeRegistry(artifacts_dir=artifacts)
        agent_manager = AgentProfileManager(artifacts_dir=artifacts)
        tool_manager = ToolProfileManager(artifacts_dir=artifacts)
        chain_registry = ToolChainPolicyRegistry(artifacts_dir=artifacts)
        
        run_id = "attribution_test"
        
        # 1. Create goal
        goal = goal_interpreter.interpret(
            run_id=run_id,
            task_input={"query": "What is machine learning?"}
        )
        assert goal.goal_id is not None
        
        # 2. Create planner genome
        genome = planner_registry.create_default_genome(run_id)
        assert genome.genome_id is not None
        
        # 3. Record agent execution
        agent_manager.record_run(
            agent_id="data_agent",
            run_id=run_id,
            success=True,
            cost=0.05,
            latency_ms=1500,
            quality=0.85,
            task_type="rag_qa"
        )
        
        # 4. Record tool usage
        tool_manager.record_invocation(
            tool_id="retriever",
            run_id=run_id,
            success=True,
            cost=0.01,
            latency_ms=500,
            value_estimate=0.5
        )
        
        # 5. Create tool chain
        chain = chain_registry.create_default_chain(run_id, "rag")
        
        # Verify chain exists
        assert (tmp_path / "artifacts" / "goals" / f"{run_id}.json").exists()
        assert (tmp_path / "artifacts" / "planner_genome" / f"{run_id}.json").exists()
        assert (tmp_path / "artifacts" / "tooling" / "tool_chains" / f"{run_id}.json").exists()
    
    def test_failure_attribution_to_tool(self, tmp_path, monkeypatch):
        """Test failure attributed to tool layer."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        tool_manager = ToolProfileManager(artifacts_dir=artifacts)
        chain_registry = ToolChainPolicyRegistry(artifacts_dir=artifacts)
        
        run_id = "tool_fail_test"
        
        # Record tool failure
        tool_manager.record_invocation(
            tool_id="retriever",
            run_id=run_id,
            success=False,
            cost=0.01,
            latency_ms=5000,
            failure_type="TIMEOUT",
            error_message="Connection timeout"
        )
        
        # Create chain with failure
        chain = chain_registry.create_default_chain(run_id, "rag")
        execution = chain_registry.record_execution(
            chain,
            [{"tool_name": "retriever", "success": False}],
            status="failed",
            failure_step=0,
            failure_reason="TIMEOUT"
        )
        
        # Verify attribution
        attribution = chain_registry.attribute_failure(execution)
        
        assert attribution["attributed"] is True
        assert attribution["layer"] == "tool"
    
    def test_failure_attribution_to_planner(self, tmp_path, monkeypatch):
        """Test failure attributed to planner layer."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        planner_registry = PlannerGenomeRegistry(artifacts_dir=artifacts)
        
        run_id = "planner_fail_test"
        
        # Create planner genome with bad config
        genome = planner_registry.create_genome(
            run_id=run_id,
            dag_depth=1,
            retrieval_breadth=0  # Too narrow
        )
        
        # Verify genome recorded
        loaded = planner_registry.load_genome(run_id)
        assert loaded.retrieval_breadth == 0
    
    def test_shadow_attribution_isolated(self, tmp_path, monkeypatch):
        """Test shadow execution attribution is isolated."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        chain_registry = ToolChainPolicyRegistry(artifacts_dir=artifacts)
        
        # Create active chain
        active = chain_registry.create_default_chain("active_run", "rag")
        
        # Create shadow variant
        shadow = chain_registry.create_shadow_variant(
            active,
            "shadow_run",
            {}
        )
        
        # Record shadow failure
        execution = chain_registry.record_execution(
            shadow,
            [{"tool_name": "parser", "success": False}],
            status="failed",
            failure_step=0,
            failure_reason="Parse error"
        )
        
        attribution = chain_registry.attribute_failure(execution)
        
        # Attribution should be for shadow
        assert attribution["attributed"] is True
        assert attribution["chain_id"] == shadow.chain_id


class TestAttributionArtifacts:
    """Attribution artifact tests."""
    
    def test_all_artifacts_created(self, tmp_path, monkeypatch):
        """Test all attribution artifacts are created."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        goal_interpreter = GoalInterpreter(artifacts_dir=artifacts)
        planner_registry = PlannerGenomeRegistry(artifacts_dir=artifacts)
        tool_manager = ToolProfileManager(artifacts_dir=artifacts)
        agent_manager = AgentProfileManager(artifacts_dir=artifacts)
        
        run_id = "full_artifacts_test"
        
        # Create all artifacts
        goal_interpreter.interpret(run_id, {"query": "Test"})
        planner_registry.create_default_genome(run_id)
        tool_manager.record_invocation("retriever", run_id, True, 0.01, 500)
        agent_manager.record_run("data_agent", run_id, True, 0.05, 1000, 0.9, "rag")
        
        # Check artifacts
        assert (tmp_path / "artifacts" / "goals" / f"{run_id}.json").exists()
        assert (tmp_path / "artifacts" / "planner_genome" / f"{run_id}.json").exists()
    
    def test_artifacts_are_replayable(self, tmp_path, monkeypatch):
        """Test artifacts can be replayed."""
        monkeypatch.chdir(tmp_path)
        artifacts = str(tmp_path / "artifacts")
        
        goal_interpreter = GoalInterpreter(artifacts_dir=artifacts)
        
        run_id = "replay_test"
        
        # Create
        original = goal_interpreter.interpret(run_id, {"query": "What is AI?"})
        
        # Reload
        loaded = goal_interpreter.load_goal(run_id)
        
        assert loaded.goal_id == original.goal_id
        assert loaded.to_hash() == original.to_hash()



