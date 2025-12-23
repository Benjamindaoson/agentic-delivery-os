"""
Agent-Level Long-Term Memory
L5 Core Component: Each agent maintains its own memory profile
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
from collections import defaultdict


class SuccessPattern(BaseModel):
    """Pattern of successful execution"""
    pattern_id: str
    goal_type: str
    tool_sequence: List[str]
    avg_quality_score: float
    success_count: int
    avg_cost: float
    avg_latency_ms: float
    context_features: Dict[str, Any]
    last_seen: datetime


class FailurePattern(BaseModel):
    """Pattern of failed execution"""
    pattern_id: str
    goal_type: str
    tool_sequence: List[str]
    failure_count: int
    failure_reasons: List[str]
    avg_attempted_cost: float
    last_seen: datetime


class ToolPreference(BaseModel):
    """Agent's tool usage preferences"""
    tool_id: str
    usage_count: int
    success_rate: float
    avg_quality_contribution: float
    preferred_for_goal_types: List[str]


class AgentMemoryProfile(BaseModel):
    """Complete memory profile for an agent"""
    agent_id: str
    total_runs: int
    total_successes: int
    total_failures: int
    overall_success_rate: float
    success_patterns: List[SuccessPattern]
    failure_patterns: List[FailurePattern]
    tool_preferences: List[ToolPreference]
    cost_stats: Dict[str, float]  # min, max, avg, total
    latency_stats: Dict[str, float]  # min, max, avg
    goal_type_affinity: Dict[str, float]  # goal_type -> success_rate
    learned_heuristics: List[str]
    last_updated: datetime = Field(default_factory=datetime.now)


class AgentMemory:
    """
    Long-term memory manager for individual agents
    Tracks patterns, preferences, and learns from history
    """
    
    def __init__(self, agent_id: str, storage_path: str = "memory/agent_profiles"):
        self.agent_id = agent_id
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
        self.profile = self._load_or_create_profile()
    
    def _load_or_create_profile(self) -> AgentMemoryProfile:
        """Load existing profile or create new one"""
        path = os.path.join(self.storage_path, f"{self.agent_id}.json")
        
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return AgentMemoryProfile(**data)
        
        # Create new profile
        return AgentMemoryProfile(
            agent_id=self.agent_id,
            total_runs=0,
            total_successes=0,
            total_failures=0,
            overall_success_rate=0.0,
            success_patterns=[],
            failure_patterns=[],
            tool_preferences=[],
            cost_stats={"min": 0.0, "max": 0.0, "avg": 0.0, "total": 0.0},
            latency_stats={"min": 0, "max": 0, "avg": 0},
            goal_type_affinity={},
            learned_heuristics=[]
        )
    
    def record_run(
        self,
        goal_type: str,
        tools_used: List[str],
        success: bool,
        quality_score: float,
        cost: float,
        latency_ms: float,
        failure_reason: Optional[str] = None
    ):
        """Record a run execution"""
        self.profile.total_runs += 1
        
        if success:
            self.profile.total_successes += 1
            self._update_success_pattern(goal_type, tools_used, quality_score, cost, latency_ms)
        else:
            self.profile.total_failures += 1
            self._update_failure_pattern(goal_type, tools_used, failure_reason or "unknown")
        
        # Update success rate
        self.profile.overall_success_rate = self.profile.total_successes / self.profile.total_runs
        
        # Update goal type affinity
        if goal_type not in self.profile.goal_type_affinity:
            self.profile.goal_type_affinity[goal_type] = 0.0
        
        # Exponential moving average
        alpha = 0.1
        current_affinity = self.profile.goal_type_affinity[goal_type]
        self.profile.goal_type_affinity[goal_type] = (
            alpha * (1.0 if success else 0.0) + (1 - alpha) * current_affinity
        )
        
        # Update tool preferences
        self._update_tool_preferences(tools_used, success, quality_score, goal_type)
        
        # Update cost/latency stats
        self._update_cost_stats(cost)
        self._update_latency_stats(latency_ms)
        
        # Update timestamp
        self.profile.last_updated = datetime.now()
        
        # Save profile
        self.save()
    
    def _update_success_pattern(
        self,
        goal_type: str,
        tools: List[str],
        quality: float,
        cost: float,
        latency: float
    ):
        """Update success pattern statistics"""
        pattern_signature = f"{goal_type}::{','.join(sorted(tools))}"
        
        # Find existing pattern
        existing = next(
            (p for p in self.profile.success_patterns if p.pattern_id == pattern_signature),
            None
        )
        
        if existing:
            # Update existing pattern
            n = existing.success_count
            existing.avg_quality_score = (existing.avg_quality_score * n + quality) / (n + 1)
            existing.avg_cost = (existing.avg_cost * n + cost) / (n + 1)
            existing.avg_latency_ms = (existing.avg_latency_ms * n + latency) / (n + 1)
            existing.success_count += 1
            existing.last_seen = datetime.now()
        else:
            # Create new pattern
            new_pattern = SuccessPattern(
                pattern_id=pattern_signature,
                goal_type=goal_type,
                tool_sequence=tools,
                avg_quality_score=quality,
                success_count=1,
                avg_cost=cost,
                avg_latency_ms=latency,
                context_features={},
                last_seen=datetime.now()
            )
            self.profile.success_patterns.append(new_pattern)
    
    def _update_failure_pattern(self, goal_type: str, tools: List[str], reason: str):
        """Update failure pattern statistics"""
        pattern_signature = f"{goal_type}::{','.join(sorted(tools))}"
        
        existing = next(
            (p for p in self.profile.failure_patterns if p.pattern_id == pattern_signature),
            None
        )
        
        if existing:
            existing.failure_count += 1
            if reason not in existing.failure_reasons:
                existing.failure_reasons.append(reason)
            existing.last_seen = datetime.now()
        else:
            new_pattern = FailurePattern(
                pattern_id=pattern_signature,
                goal_type=goal_type,
                tool_sequence=tools,
                failure_count=1,
                failure_reasons=[reason],
                avg_attempted_cost=0.0,
                last_seen=datetime.now()
            )
            self.profile.failure_patterns.append(new_pattern)
    
    def _update_tool_preferences(
        self,
        tools: List[str],
        success: bool,
        quality: float,
        goal_type: str
    ):
        """Update tool preference statistics"""
        for tool in tools:
            existing = next(
                (p for p in self.profile.tool_preferences if p.tool_id == tool),
                None
            )
            
            if existing:
                n = existing.usage_count
                existing.success_rate = (existing.success_rate * n + (1.0 if success else 0.0)) / (n + 1)
                existing.avg_quality_contribution = (existing.avg_quality_contribution * n + quality) / (n + 1)
                existing.usage_count += 1
                
                if goal_type not in existing.preferred_for_goal_types and success:
                    existing.preferred_for_goal_types.append(goal_type)
            else:
                new_pref = ToolPreference(
                    tool_id=tool,
                    usage_count=1,
                    success_rate=1.0 if success else 0.0,
                    avg_quality_contribution=quality,
                    preferred_for_goal_types=[goal_type] if success else []
                )
                self.profile.tool_preferences.append(new_pref)
    
    def _update_cost_stats(self, cost: float):
        """Update cost statistics"""
        stats = self.profile.cost_stats
        n = self.profile.total_runs
        
        if n == 1:
            stats["min"] = cost
            stats["max"] = cost
            stats["avg"] = cost
            stats["total"] = cost
        else:
            stats["min"] = min(stats["min"], cost)
            stats["max"] = max(stats["max"], cost)
            stats["avg"] = (stats["avg"] * (n - 1) + cost) / n
            stats["total"] += cost
    
    def _update_latency_stats(self, latency: float):
        """Update latency statistics"""
        stats = self.profile.latency_stats
        n = self.profile.total_runs
        
        if n == 1:
            stats["min"] = latency
            stats["max"] = latency
            stats["avg"] = latency
        else:
            stats["min"] = min(stats["min"], latency)
            stats["max"] = max(stats["max"], latency)
            stats["avg"] = (stats["avg"] * (n - 1) + latency) / n
    
    def get_best_patterns_for_goal(self, goal_type: str, top_k: int = 3) -> List[SuccessPattern]:
        """Retrieve best success patterns for a goal type"""
        relevant = [p for p in self.profile.success_patterns if p.goal_type == goal_type]
        sorted_patterns = sorted(relevant, key=lambda p: p.avg_quality_score, reverse=True)
        return sorted_patterns[:top_k]
    
    def get_preferred_tools_for_goal(self, goal_type: str, top_k: int = 5) -> List[str]:
        """Get preferred tools for a goal type"""
        relevant = [
            (p.tool_id, p.success_rate)
            for p in self.profile.tool_preferences
            if goal_type in p.preferred_for_goal_types
        ]
        sorted_tools = sorted(relevant, key=lambda x: x[1], reverse=True)
        return [tool_id for tool_id, _ in sorted_tools[:top_k]]
    
    def should_avoid_pattern(self, goal_type: str, tools: List[str]) -> bool:
        """Check if a pattern should be avoided"""
        pattern_sig = f"{goal_type}::{','.join(sorted(tools))}"
        
        for failure_pattern in self.profile.failure_patterns:
            if failure_pattern.pattern_id == pattern_sig:
                # Avoid if failure rate > 50%
                return failure_pattern.failure_count > 2
        
        return False
    
    def learn_heuristics(self):
        """Extract heuristics from patterns"""
        heuristics = []
        
        # Heuristic 1: Best tools for each goal type
        for goal_type in self.profile.goal_type_affinity.keys():
            best_tools = self.get_preferred_tools_for_goal(goal_type, top_k=3)
            if best_tools:
                heuristics.append(f"For {goal_type}, prefer: {', '.join(best_tools)}")
        
        # Heuristic 2: Cost-effective patterns
        cost_effective = [
            p for p in self.profile.success_patterns
            if p.avg_cost < self.profile.cost_stats.get("avg", float('inf')) and p.avg_quality_score > 0.8
        ]
        if cost_effective:
            heuristics.append(f"Cost-effective patterns: {len(cost_effective)} identified")
        
        # Heuristic 3: Failure avoidance
        frequent_failures = [
            p for p in self.profile.failure_patterns
            if p.failure_count >= 3
        ]
        if frequent_failures:
            heuristics.append(f"Avoid {len(frequent_failures)} known failure patterns")
        
        self.profile.learned_heuristics = heuristics
    
    def save(self):
        """Persist profile to disk"""
        path = os.path.join(self.storage_path, f"{self.agent_id}.json")
        with open(path, 'w') as f:
            f.write(self.profile.model_dump_json(indent=2))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get human-readable summary"""
        return {
            "agent_id": self.agent_id,
            "total_runs": self.profile.total_runs,
            "success_rate": f"{self.profile.overall_success_rate:.1%}",
            "best_goal_types": sorted(
                self.profile.goal_type_affinity.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3],
            "most_used_tools": [
                (p.tool_id, p.usage_count)
                for p in sorted(self.profile.tool_preferences, key=lambda x: x.usage_count, reverse=True)[:5]
            ],
            "learned_heuristics": self.profile.learned_heuristics
        }



