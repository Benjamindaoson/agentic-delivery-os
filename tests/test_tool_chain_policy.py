"""
Tests for Tool Chain Policy.
Validates tool chain failure attribution.
"""
import os
import pytest

from runtime.tooling.tool_chain_policy import (
    ToolChainPolicyRegistry,
    ToolChain,
    ToolChainExecution
)


class TestToolChainPolicy:
    """Tool chain policy tests."""
    
    def test_create_chain(self, tmp_path, monkeypatch):
        """Test creating a tool chain."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        steps = [
            {"tool_name": "parser", "tool_version": "1.0"},
            {"tool_name": "processor", "tool_version": "1.0"},
            {"tool_name": "responder", "tool_version": "1.0"}
        ]
        
        chain = registry.create_chain("test_run", "test_chain", steps)
        
        assert chain.chain_id is not None
        assert chain.run_id == "test_run"
        assert len(chain.steps) == 3
        
        # Artifact exists
        artifact_path = tmp_path / "artifacts" / "tooling" / "tool_chains" / "test_run.json"
        assert artifact_path.exists()
    
    def test_create_default_chain(self, tmp_path, monkeypatch):
        """Test creating a default RAG chain."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        chain = registry.create_default_chain("rag_run", "rag")
        
        assert len(chain.steps) >= 4
        
        tool_names = [s.tool_name for s in chain.steps]
        assert "retriever" in tool_names
        assert "llm_generator" in tool_names
    
    def test_chain_is_hashable(self, tmp_path, monkeypatch):
        """Test chain can be hashed."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        chain = registry.create_default_chain("hash_run", "rag")
        
        hash1 = chain.to_hash()
        assert len(hash1) == 16
        
        # Same chain should produce same hash
        chain2 = registry.load_chain("hash_run")
        hash2 = chain2.to_hash()
        
        assert hash1 == hash2
    
    def test_shadow_variant(self, tmp_path, monkeypatch):
        """Test creating shadow variant."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        base = registry.create_default_chain("base_run", "rag")
        shadow = registry.create_shadow_variant(
            base,
            "shadow_run",
            {"parallel_allowed": True}
        )
        
        assert shadow.chain_type == "shadow"
        assert shadow.parent_chain_id == base.chain_id
        assert shadow.parallel_allowed is True
    
    def test_record_execution(self, tmp_path, monkeypatch):
        """Test recording execution."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        chain = registry.create_default_chain("exec_run", "rag")
        
        step_results = [
            {"tool_name": "parser", "success": True, "latency_ms": 100},
            {"tool_name": "processor", "success": True, "latency_ms": 200},
            {"tool_name": "responder", "success": False, "latency_ms": 300}
        ]
        
        execution = registry.record_execution(
            chain,
            step_results,
            status="failed",
            failure_step=2,
            failure_reason="Responder timeout"
        )
        
        assert execution.status == "failed"
        assert execution.failure_step == 2
        assert execution.total_latency_ms == 600
    
    def test_failure_attribution(self, tmp_path, monkeypatch):
        """Test failure attribution to chain segment."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        chain = registry.create_default_chain("attr_run", "rag")
        
        step_results = [
            {"tool_name": "parser", "success": True, "latency_ms": 100}
        ]
        
        execution = registry.record_execution(
            chain,
            step_results,
            status="failed",
            failure_step=0,
            failure_reason="Parser error"
        )
        
        attribution = registry.attribute_failure(execution)
        
        assert attribution["attributed"] is True
        assert attribution["layer"] == "tool"
        assert attribution["segment"] == "early"


class TestToolChainShadowExecution:
    """Shadow execution tests."""
    
    def test_shadow_no_side_effects(self, tmp_path, monkeypatch):
        """Test shadow chains don't affect active."""
        monkeypatch.chdir(tmp_path)
        
        registry = ToolChainPolicyRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        active = registry.create_default_chain("active_run", "rag")
        shadow = registry.create_shadow_variant(active, "shadow_run", {})
        
        # Shadow should be independent
        assert active.chain_id != shadow.chain_id
        assert shadow.chain_type == "shadow"
        
        # Active chain unchanged
        loaded_active = registry.load_chain("active_run")
        assert loaded_active.chain_type == "active"



