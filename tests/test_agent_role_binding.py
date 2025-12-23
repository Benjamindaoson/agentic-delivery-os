"""
Tests for Agent Registry, Role Spec, and Policy Binding.
Validates agent role attribution correctness.
"""
import os
import pytest

from runtime.agents.agent_registry import (
    AgentRegistry,
    AgentDefinition,
    AgentCapability,
    InputContract,
    OutputContract,
    FailureMode
)
from runtime.agents.role_spec import RoleSpecRegistry, RoleSpec
from runtime.agents.agent_policy_binding import (
    AgentPolicyBindingRegistry,
    PolicyBinding
)


class TestAgentRegistry:
    """Agent registry tests."""
    
    def test_default_agents_registered(self, tmp_path, monkeypatch):
        """Test default agents are registered."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        agents = registry.list_all()
        assert len(agents) >= 6  # At least 6 default agents
        
        # Check specific agents exist
        assert registry.get("product_agent") is not None
        assert registry.get("data_agent") is not None
        assert registry.get("execution_agent") is not None
        assert registry.get("evaluation_agent") is not None
        assert registry.get("cost_agent") is not None
        assert registry.get("orchestrator_agent") is not None
    
    def test_agent_has_contracts(self, tmp_path, monkeypatch):
        """Test agents have input/output contracts."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        for agent in registry.list_all():
            assert agent.input_contract is not None
            assert agent.output_contract is not None
            assert len(agent.input_contract.required_fields) > 0
            assert len(agent.output_contract.guaranteed_fields) > 0
    
    def test_agent_has_failure_modes(self, tmp_path, monkeypatch):
        """Test agents have defined failure modes."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        for agent in registry.list_all():
            assert len(agent.failure_modes) > 0
            
            for mode in agent.failure_modes:
                assert mode.mode_id is not None
                assert mode.attribution_layer is not None
    
    def test_get_by_capability(self, tmp_path, monkeypatch):
        """Test finding agents by capability."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        retrievers = registry.get_by_capability(AgentCapability.RETRIEVE)
        assert len(retrievers) > 0
        
        planners = registry.get_by_capability(AgentCapability.PLAN)
        assert len(planners) > 0
    
    def test_export_snapshot(self, tmp_path, monkeypatch):
        """Test registry snapshot export."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        snapshot = registry.export_snapshot()
        
        assert "schema_version" in snapshot
        assert "agents" in snapshot
        assert len(snapshot["agents"]) > 0
        
        # Artifact exists
        artifact_path = tmp_path / "artifacts" / "agents" / "registry_snapshot.json"
        assert artifact_path.exists()
    
    def test_failure_modes_by_layer(self, tmp_path, monkeypatch):
        """Test getting failure modes by attribution layer."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        tool_failures = registry.get_failure_modes_for_layer("tool")
        retrieval_failures = registry.get_failure_modes_for_layer("retrieval")
        
        assert len(tool_failures) > 0
        assert len(retrieval_failures) > 0


class TestRoleSpec:
    """Role specification tests."""
    
    def test_default_roles_registered(self, tmp_path, monkeypatch):
        """Test default roles are registered."""
        monkeypatch.chdir(tmp_path)
        
        registry = RoleSpecRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        roles = registry.list_all()
        assert len(roles) >= 5
        
        assert registry.get("retriever") is not None
        assert registry.get("generator") is not None
        assert registry.get("validator") is not None
    
    def test_role_has_requirements(self, tmp_path, monkeypatch):
        """Test roles have input/output requirements."""
        monkeypatch.chdir(tmp_path)
        
        registry = RoleSpecRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        for role in registry.list_all():
            assert len(role.input_requirements) > 0
            assert len(role.output_requirements) > 0
    
    def test_role_assignment(self, tmp_path, monkeypatch):
        """Test role assignment to agent."""
        monkeypatch.chdir(tmp_path)
        
        registry = RoleSpecRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        assignment = registry.assign_role(
            run_id="test_run",
            role_id="retriever",
            agent_id="data_agent",
            task_type="rag"
        )
        
        assert assignment.assignment_id is not None
        assert assignment.role_id == "retriever"
        assert assignment.agent_id == "data_agent"
        assert assignment.status == "assigned"
        
        # Artifact exists
        artifact_path = tmp_path / "artifacts" / "agents" / "role_assignments" / "test_run.json"
        assert artifact_path.exists()
    
    def test_role_has_learning_signals(self, tmp_path, monkeypatch):
        """Test roles declare learning signals."""
        monkeypatch.chdir(tmp_path)
        
        registry = RoleSpecRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        retriever = registry.get("retriever")
        assert len(retriever.learning_signals_consumed) > 0
        assert len(retriever.learning_signals_produced) > 0


class TestAgentPolicyBinding:
    """Agent policy binding tests."""
    
    def test_create_binding(self, tmp_path, monkeypatch):
        """Test creating a policy binding."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentPolicyBindingRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        binding = registry.bind(
            agent_id="data_agent",
            role_id="retriever",
            policy_id="retrieval_policy_v1",
            policy_version="1.0"
        )
        
        assert binding.binding_id is not None
        assert binding.agent_id == "data_agent"
        assert binding.policy_id == "retrieval_policy_v1"
    
    def test_resolve_binding(self, tmp_path, monkeypatch):
        """Test resolving effective binding."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentPolicyBindingRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Create global binding
        registry.bind(
            agent_id="data_agent",
            role_id="retriever",
            policy_id="global_policy",
            policy_version="1.0",
            priority=5
        )
        
        # Create run-specific binding
        registry.bind(
            agent_id="data_agent",
            role_id="retriever",
            policy_id="run_policy",
            policy_version="2.0",
            run_id="test_run",
            priority=8
        )
        
        # Resolve should return run-specific (higher priority)
        resolved = registry.resolve_binding(
            agent_id="data_agent",
            role_id="retriever",
            run_id="test_run"
        )
        
        assert resolved is not None
        assert resolved.policy_id == "run_policy"
    
    def test_shadow_bindings(self, tmp_path, monkeypatch):
        """Test shadow bindings don't affect active."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentPolicyBindingRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Active binding
        registry.bind(
            agent_id="data_agent",
            role_id="retriever",
            policy_id="active_policy",
            policy_version="1.0",
            binding_type="active"
        )
        
        # Shadow binding
        registry.bind(
            agent_id="data_agent",
            role_id="retriever",
            policy_id="shadow_policy",
            policy_version="2.0",
            binding_type="shadow",
            run_id="shadow_run"
        )
        
        # Without include_shadow, should get active
        resolved = registry.resolve_binding(
            agent_id="data_agent",
            role_id="retriever",
            run_id="shadow_run",
            include_shadow=False
        )
        
        assert resolved.policy_id == "active_policy"
    
    def test_create_binding_set(self, tmp_path, monkeypatch):
        """Test creating complete binding set."""
        monkeypatch.chdir(tmp_path)
        
        registry = AgentPolicyBindingRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        # Create bindings
        registry.bind("data_agent", "retriever", "policy_a", "1.0")
        registry.bind("execution_agent", "executor", "policy_b", "1.0")
        
        binding_set = registry.create_binding_set(
            run_id="full_run",
            agent_role_pairs=[
                ("data_agent", "retriever"),
                ("execution_agent", "executor")
            ]
        )
        
        assert len(binding_set.bindings) >= 0
        assert binding_set.run_id == "full_run"
        
        # Artifact exists
        artifact_path = tmp_path / "artifacts" / "agents" / "policy_binding" / "full_run.json"
        assert artifact_path.exists()



