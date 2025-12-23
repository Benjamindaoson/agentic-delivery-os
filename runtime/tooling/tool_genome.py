"""
Tool Genome: Treat tool selection + parameters as mutable, comparable genome.
L5-grade: Tool configurations are explicit, evolvable, shadow-compatible.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class ToolConfig:
    """Configuration for a single tool."""
    tool_name: str
    tool_version: str
    enabled: bool = True
    
    # Parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Execution settings
    timeout_ms: int = 10000
    max_retries: int = 2
    retry_delay_ms: int = 1000
    
    # Fallbacks
    fallback_tool: Optional[str] = None
    fallback_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_hash(self) -> str:
        """Generate hash for this config."""
        content = json.dumps({
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "params": self.params
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:8]


@dataclass
class ToolGenome:
    """
    Genome representation of tool selection and configuration.
    
    Hashable, comparable, evolvable.
    """
    genome_id: str
    run_id: str
    
    # Tool configurations
    tools: List[ToolConfig]
    
    # Selection strategy
    selection_strategy: str = "sequential"  # sequential, parallel, conditional
    
    # Global settings
    global_timeout_ms: int = 120000
    global_max_retries: int = 3
    fail_fast: bool = True
    
    # Evolution tracking
    parent_genome_id: Optional[str] = None
    mutation_applied: Optional[str] = None
    generation: int = 0
    
    # Metadata
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "run_id": self.run_id,
            "tools": [t.to_dict() for t in self.tools],
            "selection_strategy": self.selection_strategy,
            "global_timeout_ms": self.global_timeout_ms,
            "global_max_retries": self.global_max_retries,
            "fail_fast": self.fail_fast,
            "parent_genome_id": self.parent_genome_id,
            "mutation_applied": self.mutation_applied,
            "generation": self.generation,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }
    
    def to_hash(self) -> str:
        """Generate deterministic hash for comparison."""
        hashable = {
            "tools": [t.to_hash() for t in self.tools],
            "selection_strategy": self.selection_strategy,
            "fail_fast": self.fail_fast
        }
        content = json.dumps(hashable, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names."""
        return [t.tool_name for t in self.tools if t.enabled]
    
    def get_tool_config(self, tool_name: str) -> Optional[ToolConfig]:
        """Get config for a specific tool."""
        for tool in self.tools:
            if tool.tool_name == tool_name:
                return tool
        return None
    
    def diff(self, other: "ToolGenome") -> Dict[str, Any]:
        """Compute diff between two genomes."""
        diffs = {}
        
        self_tools = {t.tool_name: t for t in self.tools}
        other_tools = {t.tool_name: t for t in other.tools}
        
        # Added tools
        added = set(other_tools.keys()) - set(self_tools.keys())
        if added:
            diffs["added_tools"] = list(added)
        
        # Removed tools
        removed = set(self_tools.keys()) - set(other_tools.keys())
        if removed:
            diffs["removed_tools"] = list(removed)
        
        # Modified tools
        modified = {}
        for name in set(self_tools.keys()) & set(other_tools.keys()):
            if self_tools[name].to_hash() != other_tools[name].to_hash():
                modified[name] = {
                    "from_params": self_tools[name].params,
                    "to_params": other_tools[name].params
                }
        if modified:
            diffs["modified_tools"] = modified
        
        # Strategy changes
        if self.selection_strategy != other.selection_strategy:
            diffs["selection_strategy"] = {
                "from": self.selection_strategy,
                "to": other.selection_strategy
            }
        
        return diffs


class ToolGenomeRegistry:
    """
    Registry for tool genomes.
    
    Supports:
    - Genome creation and storage
    - Mutation operations
    - Shadow comparison
    - Rollback
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.genome_dir = os.path.join(artifacts_dir, "tooling", "tool_genome")
        os.makedirs(self.genome_dir, exist_ok=True)
    
    def create_genome(
        self,
        run_id: str,
        tools: List[Dict[str, Any]],
        selection_strategy: str = "sequential",
        parent_genome_id: Optional[str] = None,
        mutation_applied: Optional[str] = None,
        generation: int = 0
    ) -> ToolGenome:
        """
        Create a tool genome.
        
        Args:
            run_id: Run identifier
            tools: List of tool configurations
            selection_strategy: Tool selection strategy
            parent_genome_id: Parent genome (for mutations)
            mutation_applied: Mutation that was applied
            generation: Generation number
            
        Returns:
            ToolGenome
        """
        tool_configs = []
        for tool_def in tools:
            tool_configs.append(ToolConfig(
                tool_name=tool_def.get("tool_name", "unknown"),
                tool_version=tool_def.get("tool_version", "1.0"),
                enabled=tool_def.get("enabled", True),
                params=tool_def.get("params", {}),
                timeout_ms=tool_def.get("timeout_ms", 10000),
                max_retries=tool_def.get("max_retries", 2),
                retry_delay_ms=tool_def.get("retry_delay_ms", 1000),
                fallback_tool=tool_def.get("fallback_tool"),
                fallback_params=tool_def.get("fallback_params", {})
            ))
        
        genome = ToolGenome(
            genome_id=self._generate_genome_id(run_id),
            run_id=run_id,
            tools=tool_configs,
            selection_strategy=selection_strategy,
            parent_genome_id=parent_genome_id,
            mutation_applied=mutation_applied,
            generation=generation
        )
        
        self._save_genome(genome)
        return genome
    
    def create_default_genome(self, run_id: str, task_type: str = "rag") -> ToolGenome:
        """Create a default genome for a task type."""
        if task_type == "rag":
            tools = [
                {"tool_name": "document_parser", "params": {"format": "auto"}},
                {"tool_name": "chunker", "params": {"chunk_size": 512, "overlap": 50}},
                {"tool_name": "embedder", "params": {"model": "default"}},
                {"tool_name": "retriever", "params": {"top_k": 5}},
                {"tool_name": "reranker", "params": {"enabled": True}},
                {"tool_name": "llm_generator", "params": {"temperature": 0.7}}
            ]
        else:
            tools = [
                {"tool_name": "processor", "params": {}},
                {"tool_name": "responder", "params": {}}
            ]
        
        return self.create_genome(run_id, tools)
    
    def load_genome(self, run_id: str) -> Optional[ToolGenome]:
        """Load genome for a run."""
        path = os.path.join(self.genome_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_genome(data)
    
    def mutate(
        self,
        genome: ToolGenome,
        mutation_type: str,
        new_run_id: str,
        mutation_params: Optional[Dict[str, Any]] = None
    ) -> ToolGenome:
        """
        Create a mutated version of a genome.
        
        Mutation types:
        - add_tool: Add a new tool
        - remove_tool: Remove a tool
        - swap_tool: Replace one tool with another
        - modify_params: Modify tool parameters
        - change_strategy: Change selection strategy
        - increase_timeout: Increase global timeout
        - decrease_timeout: Decrease global timeout
        - enable_parallel: Enable parallel execution
        """
        mutation_params = mutation_params or {}
        
        # Clone tools
        new_tools = [
            {
                "tool_name": t.tool_name,
                "tool_version": t.tool_version,
                "enabled": t.enabled,
                "params": dict(t.params),
                "timeout_ms": t.timeout_ms,
                "max_retries": t.max_retries,
                "retry_delay_ms": t.retry_delay_ms,
                "fallback_tool": t.fallback_tool,
                "fallback_params": dict(t.fallback_params)
            }
            for t in genome.tools
        ]
        
        new_strategy = genome.selection_strategy
        new_timeout = genome.global_timeout_ms
        
        if mutation_type == "add_tool":
            new_tool = mutation_params.get("tool", {"tool_name": "new_tool"})
            new_tools.append(new_tool)
        
        elif mutation_type == "remove_tool":
            tool_name = mutation_params.get("tool_name")
            new_tools = [t for t in new_tools if t["tool_name"] != tool_name]
        
        elif mutation_type == "swap_tool":
            old_name = mutation_params.get("old_tool")
            new_tool = mutation_params.get("new_tool", {"tool_name": "replacement"})
            for i, t in enumerate(new_tools):
                if t["tool_name"] == old_name:
                    new_tools[i] = new_tool
                    break
        
        elif mutation_type == "modify_params":
            tool_name = mutation_params.get("tool_name")
            param_updates = mutation_params.get("params", {})
            for t in new_tools:
                if t["tool_name"] == tool_name:
                    t["params"].update(param_updates)
                    break
        
        elif mutation_type == "change_strategy":
            new_strategy = mutation_params.get("strategy", "parallel")
        
        elif mutation_type == "increase_timeout":
            new_timeout = int(genome.global_timeout_ms * 1.5)
        
        elif mutation_type == "decrease_timeout":
            new_timeout = max(30000, int(genome.global_timeout_ms * 0.7))
        
        elif mutation_type == "enable_parallel":
            new_strategy = "parallel"
        
        elif mutation_type == "disable_parallel":
            new_strategy = "sequential"
        
        return self.create_genome(
            run_id=new_run_id,
            tools=new_tools,
            selection_strategy=new_strategy,
            parent_genome_id=genome.genome_id,
            mutation_applied=mutation_type,
            generation=genome.generation + 1
        )
    
    def compare(self, genome_a: ToolGenome, genome_b: ToolGenome) -> Dict[str, Any]:
        """Compare two genomes."""
        return {
            "genome_a_id": genome_a.genome_id,
            "genome_b_id": genome_b.genome_id,
            "genome_a_hash": genome_a.to_hash(),
            "genome_b_hash": genome_b.to_hash(),
            "identical": genome_a.to_hash() == genome_b.to_hash(),
            "diff": genome_a.diff(genome_b),
            "generation_delta": genome_b.generation - genome_a.generation
        }
    
    def rollback(self, genome: ToolGenome, new_run_id: str) -> Optional[ToolGenome]:
        """Rollback to parent genome."""
        if not genome.parent_genome_id:
            return None
        
        # Find parent in artifacts
        for filename in os.listdir(self.genome_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.genome_dir, filename)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("genome_id") == genome.parent_genome_id:
                    parent = self._dict_to_genome(data)
                    # Create new genome based on parent
                    return self.create_genome(
                        run_id=new_run_id,
                        tools=[t.to_dict() for t in parent.tools],
                        selection_strategy=parent.selection_strategy,
                        parent_genome_id=genome.genome_id,
                        mutation_applied="rollback",
                        generation=genome.generation + 1
                    )
        
        return None
    
    def _generate_genome_id(self, run_id: str) -> str:
        """Generate genome ID."""
        content = f"{run_id}:{datetime.now().isoformat()}"
        return f"tgenome_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _save_genome(self, genome: ToolGenome) -> None:
        """Save genome to artifact."""
        path = os.path.join(self.genome_dir, f"{genome.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(genome.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_genome(self, data: Dict[str, Any]) -> ToolGenome:
        """Convert dict to ToolGenome."""
        return ToolGenome(
            genome_id=data["genome_id"],
            run_id=data["run_id"],
            tools=[ToolConfig(**t) for t in data["tools"]],
            selection_strategy=data.get("selection_strategy", "sequential"),
            global_timeout_ms=data.get("global_timeout_ms", 120000),
            global_max_retries=data.get("global_max_retries", 3),
            fail_fast=data.get("fail_fast", True),
            parent_genome_id=data.get("parent_genome_id"),
            mutation_applied=data.get("mutation_applied"),
            generation=data.get("generation", 0),
            created_at=data.get("created_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



