"""
Agent Profile: Long-term agent performance tracking and profiling.
Tracks success_rate, failure_modes, cost, latency, task_type affinity.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from collections import defaultdict


@dataclass
class FailureModeStats:
    """Statistics for a specific failure mode."""
    mode_id: str
    count: int = 0
    last_occurred: Optional[str] = None
    avg_recovery_time_ms: float = 0.0
    recovery_success_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskTypeAffinity:
    """Agent's affinity for a task type."""
    task_type: str
    total_runs: int = 0
    successful_runs: int = 0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.successful_runs / self.total_runs if self.total_runs > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["success_rate"] = self.success_rate
        return result


@dataclass
class AgentProfile:
    """Long-term profile for an agent."""
    agent_id: str
    
    # Overall stats
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    
    # Derived metrics
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    
    # Failure tracking
    failure_modes: Dict[str, FailureModeStats] = field(default_factory=dict)
    
    # Task type affinity
    task_affinities: Dict[str, TaskTypeAffinity] = field(default_factory=dict)
    
    # Trend tracking
    recent_success_rate: float = 0.0  # Last 100 runs
    success_rate_trend: str = "stable"  # improving, stable, declining
    
    # Policy info
    current_policy_version: str = "1.0"
    policy_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
    
    @property
    def success_rate(self) -> float:
        return self.successful_runs / self.total_runs if self.total_runs > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "total_cost": round(self.total_cost, 4),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "avg_cost": round(self.avg_cost, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "avg_quality": round(self.avg_quality, 4),
            "failure_modes": {
                k: v.to_dict() for k, v in self.failure_modes.items()
            },
            "task_affinities": {
                k: v.to_dict() for k, v in self.task_affinities.items()
            },
            "recent_success_rate": round(self.recent_success_rate, 4),
            "success_rate_trend": self.success_rate_trend,
            "current_policy_version": self.current_policy_version,
            "policy_history": self.policy_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version
        }
    
    def record_run(
        self,
        success: bool,
        cost: float,
        latency_ms: float,
        quality: float,
        task_type: str,
        failure_mode: Optional[str] = None
    ) -> None:
        """Record a run for this agent."""
        self.total_runs += 1
        self.total_cost += cost
        self.total_latency_ms += latency_ms
        
        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1
            if failure_mode:
                self._record_failure(failure_mode)
        
        # Update averages
        self.avg_cost = self.total_cost / self.total_runs
        self.avg_latency_ms = self.total_latency_ms / self.total_runs
        self.avg_quality = (
            self.avg_quality * (self.total_runs - 1) + quality
        ) / self.total_runs
        
        # Update task affinity
        self._update_task_affinity(task_type, success, quality, latency_ms, cost)
        
        self.updated_at = datetime.now().isoformat()
    
    def _record_failure(self, failure_mode: str) -> None:
        """Record a failure mode occurrence."""
        if failure_mode not in self.failure_modes:
            self.failure_modes[failure_mode] = FailureModeStats(mode_id=failure_mode)
        
        stats = self.failure_modes[failure_mode]
        stats.count += 1
        stats.last_occurred = datetime.now().isoformat()
    
    def _update_task_affinity(
        self,
        task_type: str,
        success: bool,
        quality: float,
        latency_ms: float,
        cost: float
    ) -> None:
        """Update task type affinity."""
        if task_type not in self.task_affinities:
            self.task_affinities[task_type] = TaskTypeAffinity(task_type=task_type)
        
        affinity = self.task_affinities[task_type]
        affinity.total_runs += 1
        
        if success:
            affinity.successful_runs += 1
        
        # Rolling averages
        n = affinity.total_runs
        affinity.avg_quality = (affinity.avg_quality * (n - 1) + quality) / n
        affinity.avg_latency_ms = (affinity.avg_latency_ms * (n - 1) + latency_ms) / n
        affinity.avg_cost = (affinity.avg_cost * (n - 1) + cost) / n


class AgentProfileManager:
    """
    Manages long-term agent profiles.
    
    Provides:
    - Profile tracking across runs
    - Performance analytics
    - Task affinity analysis
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.profiles_dir = os.path.join(artifacts_dir, "agent_profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        self._profiles: Dict[str, AgentProfile] = {}
        self._load_profiles()
    
    def get_profile(self, agent_id: str) -> AgentProfile:
        """Get or create agent profile."""
        if agent_id not in self._profiles:
            self._profiles[agent_id] = AgentProfile(agent_id=agent_id)
        return self._profiles[agent_id]
    
    def record_run(
        self,
        agent_id: str,
        run_id: str,
        success: bool,
        cost: float,
        latency_ms: float,
        quality: float,
        task_type: str,
        failure_mode: Optional[str] = None
    ) -> None:
        """Record a run for an agent."""
        profile = self.get_profile(agent_id)
        profile.record_run(
            success=success,
            cost=cost,
            latency_ms=latency_ms,
            quality=quality,
            task_type=task_type,
            failure_mode=failure_mode
        )
        self._save_profile(profile)
    
    def get_best_agent_for_task(
        self,
        task_type: str,
        available_agents: List[str]
    ) -> Optional[str]:
        """Get the best agent for a task type."""
        candidates = []
        
        for agent_id in available_agents:
            profile = self.get_profile(agent_id)
            affinity = profile.task_affinities.get(task_type)
            
            if affinity and affinity.total_runs >= 5:
                score = (
                    affinity.success_rate * 0.5 +
                    affinity.avg_quality * 0.3 +
                    (1 - affinity.avg_cost) * 0.1 +
                    (1 - affinity.avg_latency_ms / 10000) * 0.1
                )
                candidates.append((agent_id, score))
        
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        return available_agents[0] if available_agents else None
    
    def get_agent_ranking(self) -> List[Dict[str, Any]]:
        """Get agents ranked by overall performance."""
        rankings = []
        
        for agent_id, profile in self._profiles.items():
            if profile.total_runs > 0:
                rankings.append({
                    "agent_id": agent_id,
                    "total_runs": profile.total_runs,
                    "success_rate": profile.success_rate,
                    "avg_quality": profile.avg_quality,
                    "avg_cost": profile.avg_cost,
                    "score": (
                        profile.success_rate * 0.4 +
                        profile.avg_quality * 0.4 +
                        (1 - min(1, profile.avg_cost)) * 0.2
                    )
                })
        
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings
    
    def export_all_profiles(self) -> Dict[str, Any]:
        """Export all profiles for analysis."""
        return {
            "exported_at": datetime.now().isoformat(),
            "total_agents": len(self._profiles),
            "profiles": {
                aid: p.to_dict() for aid, p in self._profiles.items()
            }
        }
    
    def _save_profile(self, profile: AgentProfile) -> None:
        """Save profile to artifact."""
        path = os.path.join(self.profiles_dir, f"{profile.agent_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_profiles(self) -> None:
        """Load all profiles from artifacts."""
        if not os.path.exists(self.profiles_dir):
            return
        
        for filename in os.listdir(self.profiles_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.profiles_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    profile = self._dict_to_profile(data)
                    self._profiles[profile.agent_id] = profile
                except (json.JSONDecodeError, IOError, KeyError):
                    pass
    
    def _dict_to_profile(self, data: Dict[str, Any]) -> AgentProfile:
        """Convert dict to AgentProfile."""
        failure_modes = {}
        for k, v in data.get("failure_modes", {}).items():
            failure_modes[k] = FailureModeStats(**v)
        
        task_affinities = {}
        for k, v in data.get("task_affinities", {}).items():
            # Remove computed field if present
            v_copy = {key: val for key, val in v.items() if key != "success_rate"}
            task_affinities[k] = TaskTypeAffinity(**v_copy)
        
        return AgentProfile(
            agent_id=data["agent_id"],
            total_runs=data.get("total_runs", 0),
            successful_runs=data.get("successful_runs", 0),
            failed_runs=data.get("failed_runs", 0),
            total_cost=data.get("total_cost", 0.0),
            total_latency_ms=data.get("total_latency_ms", 0.0),
            avg_cost=data.get("avg_cost", 0.0),
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            avg_quality=data.get("avg_quality", 0.0),
            failure_modes=failure_modes,
            task_affinities=task_affinities,
            recent_success_rate=data.get("recent_success_rate", 0.0),
            success_rate_trend=data.get("success_rate_trend", "stable"),
            current_policy_version=data.get("current_policy_version", "1.0"),
            policy_history=data.get("policy_history", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



