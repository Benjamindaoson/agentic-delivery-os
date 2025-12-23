"""
Planner Genome: Represent planner decisions as mutable, comparable genome.
L5-grade: Planner behavior is explicit, hashable, shadow-compatible.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class DAGShape(str, Enum):
    """DAG topology shapes."""
    LINEAR = "linear"
    BRANCHING = "branching"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    HYBRID = "hybrid"


@dataclass
class PlannerGenome:
    """
    Genome representation of planner behavior.
    
    Hashable, comparable, evolvable.
    """
    genome_id: str
    run_id: str
    
    # DAG structure
    dag_shape: DAGShape
    dag_depth: int  # Maximum depth
    dag_width: int  # Maximum parallelism
    
    # Branching behavior
    branching_threshold: float  # 0.0-1.0, when to branch
    branch_prune_ratio: float  # 0.0-1.0, how aggressively to prune
    
    # Retry behavior
    retry_depth: int  # Maximum retries per step
    retry_strategy: str  # immediate, exponential, adaptive
    
    # Retrieval behavior
    retrieval_breadth: int  # Number of sources to query
    retrieval_depth: int  # Chunks per source
    rerank_enabled: bool
    
    # Execution mode
    execution_mode: str  # normal, degraded, minimal
    parallel_execution: bool
    
    # Parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    parent_genome_id: Optional[str] = None
    mutation_applied: Optional[str] = None
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["dag_shape"] = self.dag_shape.value
        return result
    
    def to_hash(self) -> str:
        """Generate deterministic hash for comparison."""
        # Exclude metadata from hash
        hashable = {
            "dag_shape": self.dag_shape.value,
            "dag_depth": self.dag_depth,
            "dag_width": self.dag_width,
            "branching_threshold": self.branching_threshold,
            "branch_prune_ratio": self.branch_prune_ratio,
            "retry_depth": self.retry_depth,
            "retry_strategy": self.retry_strategy,
            "retrieval_breadth": self.retrieval_breadth,
            "retrieval_depth": self.retrieval_depth,
            "rerank_enabled": self.rerank_enabled,
            "execution_mode": self.execution_mode,
            "parallel_execution": self.parallel_execution,
            "params": self.params
        }
        content = json.dumps(hashable, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def diff(self, other: "PlannerGenome") -> Dict[str, Any]:
        """Compute diff between two genomes."""
        diffs = {}
        
        if self.dag_shape != other.dag_shape:
            diffs["dag_shape"] = {"from": self.dag_shape.value, "to": other.dag_shape.value}
        if self.dag_depth != other.dag_depth:
            diffs["dag_depth"] = {"from": self.dag_depth, "to": other.dag_depth}
        if self.dag_width != other.dag_width:
            diffs["dag_width"] = {"from": self.dag_width, "to": other.dag_width}
        if self.branching_threshold != other.branching_threshold:
            diffs["branching_threshold"] = {"from": self.branching_threshold, "to": other.branching_threshold}
        if self.retry_depth != other.retry_depth:
            diffs["retry_depth"] = {"from": self.retry_depth, "to": other.retry_depth}
        if self.retrieval_breadth != other.retrieval_breadth:
            diffs["retrieval_breadth"] = {"from": self.retrieval_breadth, "to": other.retrieval_breadth}
        if self.execution_mode != other.execution_mode:
            diffs["execution_mode"] = {"from": self.execution_mode, "to": other.execution_mode}
        
        return diffs


class PlannerGenomeRegistry:
    """
    Registry for planner genomes.
    
    Stores genomes per run and supports comparison across runs.
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.genome_dir = os.path.join(artifacts_dir, "planner_genome")
        os.makedirs(self.genome_dir, exist_ok=True)
    
    def create_genome(
        self,
        run_id: str,
        dag_shape: DAGShape = DAGShape.LINEAR,
        dag_depth: int = 5,
        dag_width: int = 1,
        branching_threshold: float = 0.7,
        branch_prune_ratio: float = 0.5,
        retry_depth: int = 2,
        retry_strategy: str = "exponential",
        retrieval_breadth: int = 3,
        retrieval_depth: int = 5,
        rerank_enabled: bool = True,
        execution_mode: str = "normal",
        parallel_execution: bool = False,
        params: Optional[Dict[str, Any]] = None,
        parent_genome_id: Optional[str] = None,
        mutation_applied: Optional[str] = None
    ) -> PlannerGenome:
        """Create a new planner genome."""
        genome = PlannerGenome(
            genome_id=f"genome_{run_id}_{datetime.now().strftime('%H%M%S')}",
            run_id=run_id,
            dag_shape=dag_shape,
            dag_depth=dag_depth,
            dag_width=dag_width,
            branching_threshold=branching_threshold,
            branch_prune_ratio=branch_prune_ratio,
            retry_depth=retry_depth,
            retry_strategy=retry_strategy,
            retrieval_breadth=retrieval_breadth,
            retrieval_depth=retrieval_depth,
            rerank_enabled=rerank_enabled,
            execution_mode=execution_mode,
            parallel_execution=parallel_execution,
            params=params or {},
            parent_genome_id=parent_genome_id,
            mutation_applied=mutation_applied
        )
        
        self._save_genome(genome)
        return genome
    
    def create_default_genome(self, run_id: str) -> PlannerGenome:
        """Create a genome with default settings."""
        return self.create_genome(run_id)
    
    def load_genome(self, run_id: str) -> Optional[PlannerGenome]:
        """Load genome from artifact."""
        path = os.path.join(self.genome_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_genome(data)
    
    def mutate(
        self,
        genome: PlannerGenome,
        mutation_type: str,
        new_run_id: str
    ) -> PlannerGenome:
        """
        Create a mutated version of a genome.
        
        Mutation types:
        - increase_breadth: Increase retrieval breadth
        - decrease_breadth: Decrease retrieval breadth
        - increase_depth: Increase DAG depth
        - decrease_depth: Decrease DAG depth
        - enable_branching: Switch to branching DAG
        - disable_branching: Switch to linear DAG
        - increase_retries: Increase retry depth
        - decrease_retries: Decrease retry depth
        - enable_rerank: Enable reranking
        - disable_rerank: Disable reranking
        """
        # Clone with mutations
        new_params = dict(genome.params)
        
        new_dag_shape = genome.dag_shape
        new_dag_depth = genome.dag_depth
        new_dag_width = genome.dag_width
        new_branching = genome.branching_threshold
        new_retry_depth = genome.retry_depth
        new_retrieval_breadth = genome.retrieval_breadth
        new_retrieval_depth = genome.retrieval_depth
        new_rerank = genome.rerank_enabled
        new_execution_mode = genome.execution_mode
        new_parallel = genome.parallel_execution
        
        if mutation_type == "increase_breadth":
            new_retrieval_breadth = min(10, genome.retrieval_breadth + 1)
        elif mutation_type == "decrease_breadth":
            new_retrieval_breadth = max(1, genome.retrieval_breadth - 1)
        elif mutation_type == "increase_depth":
            new_dag_depth = min(10, genome.dag_depth + 1)
            new_retrieval_depth = min(10, genome.retrieval_depth + 1)
        elif mutation_type == "decrease_depth":
            new_dag_depth = max(2, genome.dag_depth - 1)
            new_retrieval_depth = max(2, genome.retrieval_depth - 1)
        elif mutation_type == "enable_branching":
            new_dag_shape = DAGShape.BRANCHING
            new_dag_width = max(2, genome.dag_width)
        elif mutation_type == "disable_branching":
            new_dag_shape = DAGShape.LINEAR
            new_dag_width = 1
        elif mutation_type == "increase_retries":
            new_retry_depth = min(5, genome.retry_depth + 1)
        elif mutation_type == "decrease_retries":
            new_retry_depth = max(0, genome.retry_depth - 1)
        elif mutation_type == "enable_rerank":
            new_rerank = True
        elif mutation_type == "disable_rerank":
            new_rerank = False
        elif mutation_type == "enable_parallel":
            new_parallel = True
            new_dag_shape = DAGShape.PARALLEL
        elif mutation_type == "disable_parallel":
            new_parallel = False
        elif mutation_type == "lower_branching_threshold":
            new_branching = max(0.3, genome.branching_threshold - 0.1)
        elif mutation_type == "raise_branching_threshold":
            new_branching = min(0.95, genome.branching_threshold + 0.1)
        
        return self.create_genome(
            run_id=new_run_id,
            dag_shape=new_dag_shape,
            dag_depth=new_dag_depth,
            dag_width=new_dag_width,
            branching_threshold=new_branching,
            branch_prune_ratio=genome.branch_prune_ratio,
            retry_depth=new_retry_depth,
            retry_strategy=genome.retry_strategy,
            retrieval_breadth=new_retrieval_breadth,
            retrieval_depth=new_retrieval_depth,
            rerank_enabled=new_rerank,
            execution_mode=new_execution_mode,
            parallel_execution=new_parallel,
            params=new_params,
            parent_genome_id=genome.genome_id,
            mutation_applied=mutation_type
        )
    
    def compare(self, genome_a: PlannerGenome, genome_b: PlannerGenome) -> Dict[str, Any]:
        """Compare two genomes and return structured diff."""
        return {
            "genome_a_id": genome_a.genome_id,
            "genome_b_id": genome_b.genome_id,
            "genome_a_hash": genome_a.to_hash(),
            "genome_b_hash": genome_b.to_hash(),
            "identical": genome_a.to_hash() == genome_b.to_hash(),
            "diff": genome_a.diff(genome_b)
        }
    
    def _save_genome(self, genome: PlannerGenome) -> None:
        """Save genome to artifact."""
        path = os.path.join(self.genome_dir, f"{genome.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(genome.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_genome(self, data: Dict[str, Any]) -> PlannerGenome:
        """Convert dict to PlannerGenome."""
        return PlannerGenome(
            genome_id=data["genome_id"],
            run_id=data["run_id"],
            dag_shape=DAGShape(data["dag_shape"]),
            dag_depth=data["dag_depth"],
            dag_width=data["dag_width"],
            branching_threshold=data["branching_threshold"],
            branch_prune_ratio=data["branch_prune_ratio"],
            retry_depth=data["retry_depth"],
            retry_strategy=data["retry_strategy"],
            retrieval_breadth=data["retrieval_breadth"],
            retrieval_depth=data["retrieval_depth"],
            rerank_enabled=data["rerank_enabled"],
            execution_mode=data["execution_mode"],
            parallel_execution=data["parallel_execution"],
            params=data.get("params", {}),
            parent_genome_id=data.get("parent_genome_id"),
            mutation_applied=data.get("mutation_applied"),
            created_at=data.get("created_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



