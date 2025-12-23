"""
Long-Term Memory: Persistent memory across runs and sessions.
Combines vector and structured storage for patterns, behaviors, and outcomes.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class MemoryEntry:
    """A single memory entry."""
    entry_id: str
    memory_type: str  # task_pattern, agent_behavior, planner_outcome, tool_usage, user_preference
    
    # Content
    content: Dict[str, Any]
    embedding: Optional[List[float]] = None
    
    # Metadata
    source_run_id: str = ""
    source_session_id: str = ""
    importance: float = 0.5  # 0.0-1.0
    access_count: int = 0
    last_accessed: str = ""
    
    # Timestamps
    created_at: str = ""
    expires_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_accessed:
            self.last_accessed = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Don't save embedding to JSON (too large)
        result.pop("embedding", None)
        return result


@dataclass
class TaskPattern:
    """A task execution pattern."""
    pattern_id: str
    task_type: str
    
    # Pattern details
    query_signature: str  # Hash of normalized query
    context_signature: str  # Hash of context
    
    # Execution path
    agents_used: List[str]
    tools_used: List[str]
    planner_decisions: List[str]
    
    # Outcomes
    success_count: int = 0
    failure_count: int = 0
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    
    # Metadata
    first_seen: str = ""
    last_seen: str = ""
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def update(self, success: bool, cost: float, latency_ms: float, quality: float) -> None:
        """Update pattern with new execution."""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        total = self.success_count + self.failure_count
        
        # Running average
        self.avg_cost = ((self.avg_cost * (total - 1)) + cost) / total
        self.avg_latency_ms = ((self.avg_latency_ms * (total - 1)) + latency_ms) / total
        self.avg_quality = ((self.avg_quality * (total - 1)) + quality) / total
        
        self.last_seen = datetime.now().isoformat()


@dataclass
class AgentBehavior:
    """Agent behavior record."""
    agent_id: str
    
    # Statistics
    total_invocations: int = 0
    successful_invocations: int = 0
    failed_invocations: int = 0
    
    # Performance
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    
    # Task affinity
    task_type_counts: Dict[str, int] = field(default_factory=dict)
    task_type_success: Dict[str, int] = field(default_factory=dict)
    
    # Failure patterns
    failure_modes: Dict[str, int] = field(default_factory=dict)
    
    # Metadata
    first_seen: str = ""
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        return self.successful_invocations / self.total_invocations if self.total_invocations > 0 else 0.0
    
    def update(
        self,
        success: bool,
        task_type: str,
        cost: float,
        latency_ms: float,
        failure_mode: Optional[str] = None
    ) -> None:
        """Update behavior with new invocation."""
        self.total_invocations += 1
        if success:
            self.successful_invocations += 1
            self.task_type_success[task_type] = self.task_type_success.get(task_type, 0) + 1
        else:
            self.failed_invocations += 1
            if failure_mode:
                self.failure_modes[failure_mode] = self.failure_modes.get(failure_mode, 0) + 1
        
        self.task_type_counts[task_type] = self.task_type_counts.get(task_type, 0) + 1
        
        # Running average
        n = self.total_invocations
        self.avg_cost = ((self.avg_cost * (n - 1)) + cost) / n
        self.avg_latency_ms = ((self.avg_latency_ms * (n - 1)) + latency_ms) / n
        
        self.last_updated = datetime.now().isoformat()


class LongTermMemory:
    """
    Long-term memory store for persistent patterns and behaviors.
    
    Features:
    - Task pattern storage and retrieval
    - Agent behavior tracking
    - Planner outcome history
    - Vector similarity search (simplified)
    """
    
    def __init__(self, storage_dir: str = "memory/long_term"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
        self._patterns: Dict[str, TaskPattern] = {}
        self._behaviors: Dict[str, AgentBehavior] = {}
        self._entries: Dict[str, MemoryEntry] = {}
        
        self._load_all()
    
    def store_task_pattern(
        self,
        task_type: str,
        query: str,
        context: Dict[str, Any],
        agents_used: List[str],
        tools_used: List[str],
        planner_decisions: List[str],
        success: bool,
        cost: float,
        latency_ms: float,
        quality: float
    ) -> TaskPattern:
        """Store or update a task pattern."""
        query_sig = self._hash_string(query.lower().strip())
        context_sig = self._hash_dict(context)
        pattern_id = f"pattern_{query_sig}_{context_sig}"
        
        if pattern_id in self._patterns:
            pattern = self._patterns[pattern_id]
            pattern.update(success, cost, latency_ms, quality)
        else:
            pattern = TaskPattern(
                pattern_id=pattern_id,
                task_type=task_type,
                query_signature=query_sig,
                context_signature=context_sig,
                agents_used=agents_used,
                tools_used=tools_used,
                planner_decisions=planner_decisions,
                success_count=1 if success else 0,
                failure_count=0 if success else 1,
                avg_cost=cost,
                avg_latency_ms=latency_ms,
                avg_quality=quality
            )
            self._patterns[pattern_id] = pattern
        
        self._save_patterns()
        return pattern
    
    def get_similar_patterns(
        self,
        task_type: str,
        limit: int = 5
    ) -> List[TaskPattern]:
        """Get similar task patterns."""
        matching = [
            p for p in self._patterns.values()
            if p.task_type == task_type
        ]
        
        # Sort by success rate and recency
        matching.sort(key=lambda p: (p.success_rate, p.last_seen), reverse=True)
        
        return matching[:limit]
    
    def get_best_pattern_for_task(self, task_type: str) -> Optional[TaskPattern]:
        """Get the best-performing pattern for a task type."""
        patterns = self.get_similar_patterns(task_type, limit=1)
        return patterns[0] if patterns else None
    
    def update_agent_behavior(
        self,
        agent_id: str,
        success: bool,
        task_type: str,
        cost: float,
        latency_ms: float,
        failure_mode: Optional[str] = None
    ) -> AgentBehavior:
        """Update agent behavior record."""
        if agent_id not in self._behaviors:
            self._behaviors[agent_id] = AgentBehavior(
                agent_id=agent_id,
                first_seen=datetime.now().isoformat()
            )
        
        behavior = self._behaviors[agent_id]
        behavior.update(success, task_type, cost, latency_ms, failure_mode)
        
        self._save_behaviors()
        return behavior
    
    def get_agent_behavior(self, agent_id: str) -> Optional[AgentBehavior]:
        """Get agent behavior record."""
        return self._behaviors.get(agent_id)
    
    def get_all_agent_behaviors(self) -> List[AgentBehavior]:
        """Get all agent behaviors."""
        return list(self._behaviors.values())
    
    def store_memory_entry(
        self,
        memory_type: str,
        content: Dict[str, Any],
        source_run_id: str = "",
        source_session_id: str = "",
        importance: float = 0.5
    ) -> MemoryEntry:
        """Store a general memory entry."""
        entry_id = f"mem_{memory_type}_{self._hash_dict(content)}"
        
        entry = MemoryEntry(
            entry_id=entry_id,
            memory_type=memory_type,
            content=content,
            source_run_id=source_run_id,
            source_session_id=source_session_id,
            importance=importance
        )
        
        self._entries[entry_id] = entry
        self._save_entries()
        
        return entry
    
    def search_entries(
        self,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Search memory entries."""
        results = []
        
        for entry in self._entries.values():
            if memory_type and entry.memory_type != memory_type:
                continue
            if entry.importance < min_importance:
                continue
            results.append(entry)
        
        # Sort by importance and recency
        results.sort(key=lambda e: (e.importance, e.last_accessed), reverse=True)
        
        return results[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_patterns": len(self._patterns),
            "total_behaviors": len(self._behaviors),
            "total_entries": len(self._entries),
            "pattern_types": list(set(p.task_type for p in self._patterns.values())),
            "agent_ids": list(self._behaviors.keys()),
            "entry_types": list(set(e.memory_type for e in self._entries.values()))
        }
    
    def _hash_string(self, s: str) -> str:
        """Hash a string."""
        return hashlib.sha256(s.encode()).hexdigest()[:12]
    
    def _hash_dict(self, d: Dict[str, Any]) -> str:
        """Hash a dictionary."""
        content = json.dumps(d, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def _save_patterns(self) -> None:
        """Save patterns to disk."""
        path = os.path.join(self.storage_dir, "patterns.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._patterns.items()},
                f, indent=2, ensure_ascii=False
            )
    
    def _save_behaviors(self) -> None:
        """Save behaviors to disk."""
        path = os.path.join(self.storage_dir, "behaviors.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._behaviors.items()},
                f, indent=2, ensure_ascii=False
            )
    
    def _save_entries(self) -> None:
        """Save entries to disk."""
        path = os.path.join(self.storage_dir, "entries.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._entries.items()},
                f, indent=2, ensure_ascii=False
            )
    
    def _load_all(self) -> None:
        """Load all data from disk."""
        self._load_patterns()
        self._load_behaviors()
        self._load_entries()
    
    def _load_patterns(self) -> None:
        """Load patterns from disk."""
        path = os.path.join(self.storage_dir, "patterns.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self._patterns[k] = TaskPattern(**v)
        except (json.JSONDecodeError, IOError):
            pass
    
    def _load_behaviors(self) -> None:
        """Load behaviors from disk."""
        path = os.path.join(self.storage_dir, "behaviors.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self._behaviors[k] = AgentBehavior(**v)
        except (json.JSONDecodeError, IOError):
            pass
    
    def _load_entries(self) -> None:
        """Load entries from disk."""
        path = os.path.join(self.storage_dir, "entries.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self._entries[k] = MemoryEntry(**v)
        except (json.JSONDecodeError, IOError):
            pass

