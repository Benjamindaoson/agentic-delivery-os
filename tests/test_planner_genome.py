"""
Tests for Planner Genome.
Validates genome stability, hashability, and mutation operations.
"""
import os
import pytest

from runtime.planning.planner_genome import (
    PlannerGenome,
    PlannerGenomeRegistry,
    DAGShape
)


class TestPlannerGenome:
    """Planner genome tests."""
    
    def test_create_default_genome(self, tmp_path, monkeypatch):
        """Test creating a default genome."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        genome = registry.create_default_genome("test_run")
        
        assert genome.genome_id is not None
        assert genome.run_id == "test_run"
        assert genome.dag_shape == DAGShape.LINEAR
        assert genome.dag_depth == 5
        
        # Artifact should exist
        artifact_path = tmp_path / "artifacts" / "planner_genome" / "test_run.json"
        assert artifact_path.exists()
    
    def test_genome_is_hashable(self, tmp_path, monkeypatch):
        """Test genome can be hashed."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        genome = registry.create_default_genome("hash_test")
        
        hash1 = genome.to_hash()
        assert len(hash1) == 16
        
        # Same genome should produce same hash
        genome2 = registry.load_genome("hash_test")
        hash2 = genome2.to_hash()
        
        assert hash1 == hash2
    
    def test_genome_mutation_increase_breadth(self, tmp_path, monkeypatch):
        """Test mutation: increase retrieval breadth."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        original = registry.create_default_genome("original")
        original_breadth = original.retrieval_breadth
        
        mutated = registry.mutate(original, "increase_breadth", "mutated")
        
        assert mutated.retrieval_breadth == original_breadth + 1
        assert mutated.parent_genome_id == original.genome_id
        assert mutated.mutation_applied == "increase_breadth"
    
    def test_genome_mutation_enable_branching(self, tmp_path, monkeypatch):
        """Test mutation: enable branching."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        original = registry.create_default_genome("linear")
        assert original.dag_shape == DAGShape.LINEAR
        
        mutated = registry.mutate(original, "enable_branching", "branching")
        
        assert mutated.dag_shape == DAGShape.BRANCHING
        assert mutated.dag_width >= 2
    
    def test_genome_diff(self, tmp_path, monkeypatch):
        """Test genome comparison."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        genome1 = registry.create_default_genome("diff1")
        genome2 = registry.mutate(genome1, "increase_breadth", "diff2")
        
        diff = genome1.diff(genome2)
        
        assert "retrieval_breadth" in diff
        assert diff["retrieval_breadth"]["from"] == genome1.retrieval_breadth
        assert diff["retrieval_breadth"]["to"] == genome2.retrieval_breadth
    
    def test_genome_compare(self, tmp_path, monkeypatch):
        """Test structured genome comparison."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        genome1 = registry.create_default_genome("cmp1")
        genome2 = registry.create_default_genome("cmp2")
        
        comparison = registry.compare(genome1, genome2)
        
        assert "genome_a_id" in comparison
        assert "genome_b_id" in comparison
        assert "identical" in comparison
        assert "diff" in comparison
        
        # Same defaults should be identical
        assert comparison["identical"] is True
    
    def test_genome_is_shadow_compatible(self, tmp_path, monkeypatch):
        """Test genome can be used in shadow execution."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        active = registry.create_default_genome("active_run")
        shadow = registry.mutate(active, "increase_depth", "shadow_run")
        
        # Both should be independent
        assert active.genome_id != shadow.genome_id
        assert active.to_hash() != shadow.to_hash()
        
        # Shadow should track lineage
        assert shadow.parent_genome_id == active.genome_id


class TestPlannerGenomeStability:
    """Test genome stability across operations."""
    
    def test_genome_reload_stable(self, tmp_path, monkeypatch):
        """Test genome is stable across save/load."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        original = registry.create_genome(
            run_id="stable_test",
            dag_shape=DAGShape.BRANCHING,
            dag_depth=7,
            retrieval_breadth=5
        )
        
        loaded = registry.load_genome("stable_test")
        
        assert loaded.dag_shape == original.dag_shape
        assert loaded.dag_depth == original.dag_depth
        assert loaded.retrieval_breadth == original.retrieval_breadth
        assert loaded.to_hash() == original.to_hash()
    
    def test_mutation_chain_stable(self, tmp_path, monkeypatch):
        """Test chain of mutations is stable."""
        monkeypatch.chdir(tmp_path)
        
        registry = PlannerGenomeRegistry(artifacts_dir=str(tmp_path / "artifacts"))
        
        g0 = registry.create_default_genome("gen0")
        g1 = registry.mutate(g0, "increase_breadth", "gen1")
        g2 = registry.mutate(g1, "increase_depth", "gen2")
        g3 = registry.mutate(g2, "enable_parallel", "gen3")
        
        # Each generation should be different
        hashes = [g0.to_hash(), g1.to_hash(), g2.to_hash(), g3.to_hash()]
        assert len(set(hashes)) == 4
        
        # Lineage should be traceable
        assert g1.parent_genome_id == g0.genome_id
        assert g2.parent_genome_id == g1.genome_id
        assert g3.parent_genome_id == g2.genome_id



