"""
Tool Chain Policy: Represent tool usage as ordered chain, support A/B and shadow.
L5-grade: Tool chains are explicit, attributable, evolvable.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class ToolChainStep:
    """A single step in a tool chain."""
    step_id: str
    step_index: int
    tool_name: str
    tool_version: str
    
    # Input/output
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Execution
    timeout_ms: int = 10000
    retry_count: int = 2
    fallback_tool: Optional[str] = None
    
    # Conditions
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolChain:
    """Ordered chain of tool invocations."""
    chain_id: str
    run_id: str
    chain_name: str
    
    # Steps
    steps: List[ToolChainStep]
    
    # Chain properties
    parallel_allowed: bool = False
    fail_fast: bool = True
    max_total_retries: int = 5
    
    # A/B and shadow
    chain_type: str = "active"  # active, shadow, candidate
    parent_chain_id: Optional[str] = None
    
    # Metadata
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "run_id": self.run_id,
            "chain_name": self.chain_name,
            "steps": [s.to_dict() for s in self.steps],
            "parallel_allowed": self.parallel_allowed,
            "fail_fast": self.fail_fast,
            "max_total_retries": self.max_total_retries,
            "chain_type": self.chain_type,
            "parent_chain_id": self.parent_chain_id,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }
    
    def to_hash(self) -> str:
        """Generate deterministic hash."""
        hashable = {
            "chain_name": self.chain_name,
            "steps": [
                {"tool": s.tool_name, "version": s.tool_version, "index": s.step_index}
                for s in self.steps
            ],
            "parallel_allowed": self.parallel_allowed,
            "fail_fast": self.fail_fast
        }
        content = json.dumps(hashable, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ToolChainExecution:
    """Execution record for a tool chain."""
    execution_id: str
    chain_id: str
    run_id: str
    
    # Execution state
    status: str = "pending"  # pending, running, completed, failed
    current_step: int = 0
    
    # Results per step
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_latency_ms: float = 0.0
    
    # Attribution
    failure_step: Optional[int] = None
    failure_reason: Optional[str] = None
    
    # Metadata
    schema_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolChainPolicyRegistry:
    """
    Registry for tool chain policies.
    
    Supports:
    - Active chains (affect execution)
    - Shadow chains (for A/B, no effect on output)
    - Failure attribution to chain segments
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.chains_dir = os.path.join(artifacts_dir, "tooling", "tool_chains")
        os.makedirs(self.chains_dir, exist_ok=True)
    
    def create_chain(
        self,
        run_id: str,
        chain_name: str,
        steps: List[Dict[str, Any]],
        chain_type: str = "active",
        parallel_allowed: bool = False,
        fail_fast: bool = True,
        parent_chain_id: Optional[str] = None
    ) -> ToolChain:
        """
        Create a tool chain.
        
        Args:
            run_id: Run identifier
            chain_name: Chain name
            steps: List of step definitions
            chain_type: active, shadow, or candidate
            parallel_allowed: Allow parallel execution
            fail_fast: Fail on first error
            parent_chain_id: Parent chain (for variants)
            
        Returns:
            ToolChain
        """
        chain_steps = []
        for i, step_def in enumerate(steps):
            chain_steps.append(ToolChainStep(
                step_id=f"{run_id}_step_{i}",
                step_index=i,
                tool_name=step_def.get("tool_name", "unknown"),
                tool_version=step_def.get("tool_version", "1.0"),
                input_schema=step_def.get("input_schema", {}),
                output_schema=step_def.get("output_schema", {}),
                timeout_ms=step_def.get("timeout_ms", 10000),
                retry_count=step_def.get("retry_count", 2),
                fallback_tool=step_def.get("fallback_tool"),
                preconditions=step_def.get("preconditions", []),
                postconditions=step_def.get("postconditions", [])
            ))
        
        chain = ToolChain(
            chain_id=self._generate_chain_id(run_id, chain_name),
            run_id=run_id,
            chain_name=chain_name,
            steps=chain_steps,
            parallel_allowed=parallel_allowed,
            fail_fast=fail_fast,
            chain_type=chain_type,
            parent_chain_id=parent_chain_id
        )
        
        self._save_chain(chain)
        return chain
    
    def create_default_chain(self, run_id: str, task_type: str) -> ToolChain:
        """Create a default chain based on task type."""
        if task_type == "rag":
            steps = [
                {"tool_name": "document_parser", "tool_version": "1.0", "timeout_ms": 5000},
                {"tool_name": "chunker", "tool_version": "1.0", "timeout_ms": 3000},
                {"tool_name": "embedder", "tool_version": "1.0", "timeout_ms": 5000},
                {"tool_name": "retriever", "tool_version": "1.0", "timeout_ms": 10000},
                {"tool_name": "reranker", "tool_version": "1.0", "timeout_ms": 5000},
                {"tool_name": "llm_generator", "tool_version": "1.0", "timeout_ms": 30000}
            ]
        elif task_type == "transform":
            steps = [
                {"tool_name": "input_parser", "tool_version": "1.0"},
                {"tool_name": "transformer", "tool_version": "1.0"},
                {"tool_name": "output_formatter", "tool_version": "1.0"}
            ]
        else:
            steps = [
                {"tool_name": "analyzer", "tool_version": "1.0"},
                {"tool_name": "processor", "tool_version": "1.0"},
                {"tool_name": "responder", "tool_version": "1.0"}
            ]
        
        return self.create_chain(run_id, f"{task_type}_chain", steps)
    
    def create_shadow_variant(
        self,
        chain: ToolChain,
        new_run_id: str,
        modifications: Dict[str, Any]
    ) -> ToolChain:
        """
        Create a shadow variant of a chain.
        
        Args:
            chain: Base chain
            new_run_id: New run ID
            modifications: Modifications to apply
            
        Returns:
            Shadow chain
        """
        # Clone steps with modifications
        new_steps = []
        for step in chain.steps:
            step_dict = step.to_dict()
            
            # Apply step-specific modifications
            step_mods = modifications.get("steps", {}).get(str(step.step_index), {})
            step_dict.update(step_mods)
            
            new_steps.append(step_dict)
        
        # Apply chain-level modifications
        return self.create_chain(
            run_id=new_run_id,
            chain_name=f"{chain.chain_name}_shadow",
            steps=new_steps,
            chain_type="shadow",
            parallel_allowed=modifications.get("parallel_allowed", chain.parallel_allowed),
            fail_fast=modifications.get("fail_fast", chain.fail_fast),
            parent_chain_id=chain.chain_id
        )
    
    def load_chain(self, run_id: str) -> Optional[ToolChain]:
        """Load chain for a run."""
        path = os.path.join(self.chains_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_chain(data)
    
    def record_execution(
        self,
        chain: ToolChain,
        step_results: List[Dict[str, Any]],
        status: str,
        failure_step: Optional[int] = None,
        failure_reason: Optional[str] = None
    ) -> ToolChainExecution:
        """
        Record chain execution result.
        
        Args:
            chain: Executed chain
            step_results: Results per step
            status: Final status
            failure_step: Failed step index (if any)
            failure_reason: Failure reason (if any)
            
        Returns:
            ToolChainExecution
        """
        total_latency = sum(r.get("latency_ms", 0) for r in step_results)
        
        execution = ToolChainExecution(
            execution_id=f"exec_{chain.run_id}_{chain.chain_id}",
            chain_id=chain.chain_id,
            run_id=chain.run_id,
            status=status,
            current_step=len(step_results),
            step_results=step_results,
            started_at=step_results[0].get("started_at") if step_results else None,
            completed_at=datetime.now().isoformat(),
            total_latency_ms=total_latency,
            failure_step=failure_step,
            failure_reason=failure_reason
        )
        
        self._save_execution(execution)
        return execution
    
    def attribute_failure(
        self,
        execution: ToolChainExecution
    ) -> Dict[str, Any]:
        """
        Attribute failure to chain segment.
        
        Returns attribution details for the decision attributor.
        """
        if execution.status != "failed":
            return {"attributed": False, "reason": "not_failed"}
        
        if execution.failure_step is None:
            return {"attributed": False, "reason": "unknown_step"}
        
        # Get failed step
        failed_step_result = execution.step_results[execution.failure_step] if execution.failure_step < len(execution.step_results) else None
        
        attribution = {
            "attributed": True,
            "layer": "tool",
            "chain_id": execution.chain_id,
            "failed_step_index": execution.failure_step,
            "failed_tool": failed_step_result.get("tool_name") if failed_step_result else "unknown",
            "failure_reason": execution.failure_reason,
            "segment": self._determine_segment(execution.failure_step, len(execution.step_results)),
            "retry_count": failed_step_result.get("retry_count", 0) if failed_step_result else 0
        }
        
        return attribution
    
    def _determine_segment(self, failure_step: int, total_steps: int) -> str:
        """Determine which segment of the chain failed."""
        ratio = failure_step / total_steps if total_steps > 0 else 0
        
        if ratio < 0.33:
            return "early"  # Input/parsing phase
        elif ratio < 0.66:
            return "middle"  # Processing phase
        else:
            return "late"  # Output/generation phase
    
    def _generate_chain_id(self, run_id: str, chain_name: str) -> str:
        """Generate chain ID."""
        content = f"{run_id}:{chain_name}:{datetime.now().isoformat()}"
        return f"chain_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _save_chain(self, chain: ToolChain) -> None:
        """Save chain to artifact."""
        path = os.path.join(self.chains_dir, f"{chain.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chain.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_execution(self, execution: ToolChainExecution) -> None:
        """Save execution to artifact."""
        exec_dir = os.path.join(self.chains_dir, "executions")
        os.makedirs(exec_dir, exist_ok=True)
        
        path = os.path.join(exec_dir, f"{execution.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(execution.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_chain(self, data: Dict[str, Any]) -> ToolChain:
        """Convert dict to ToolChain."""
        return ToolChain(
            chain_id=data["chain_id"],
            run_id=data["run_id"],
            chain_name=data["chain_name"],
            steps=[ToolChainStep(**s) for s in data["steps"]],
            parallel_allowed=data.get("parallel_allowed", False),
            fail_fast=data.get("fail_fast", True),
            max_total_retries=data.get("max_total_retries", 5),
            chain_type=data.get("chain_type", "active"),
            parent_chain_id=data.get("parent_chain_id"),
            created_at=data.get("created_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



