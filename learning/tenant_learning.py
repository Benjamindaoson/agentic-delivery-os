"""
Tenant-Level Learning: Enhanced multi-tenant learning capabilities
P1-2 Implementation: Tenant-local knowledge, cross-tenant patterns, cold-start, budget-learning linkage

This module provides:
1. Clear separation of tenant-local vs cross-tenant knowledge
2. Tenant-specific cold-start strategies
3. Budget → Learning intensity linkage
4. Tenant-aware policy optimization
"""

import os
import json
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


class LearningIntensity(str, Enum):
    """Learning intensity levels"""
    OFF = "off"              # No learning
    MINIMAL = "minimal"      # Basic statistics only
    STANDARD = "standard"    # Standard learning rate
    AGGRESSIVE = "aggressive"  # High learning rate, more exploration


class ColdStartStrategy(str, Enum):
    """Strategies for cold-starting new tenants"""
    DEFAULT = "default"          # Use system defaults
    CLONE_SIMILAR = "clone_similar"  # Clone from similar tenant
    META_LEARNING = "meta_learning"  # Use meta-learned policies
    CONSERVATIVE = "conservative"    # Very conservative, minimal features


@dataclass
class TenantLearningProfile:
    """Learning profile for a tenant"""
    tenant_id: str
    
    # Learning settings
    learning_enabled: bool = True
    intensity: LearningIntensity = LearningIntensity.STANDARD
    cold_start_strategy: ColdStartStrategy = ColdStartStrategy.META_LEARNING
    
    # Privacy settings
    share_patterns: bool = False  # Opt-in to share patterns
    accept_meta_learning: bool = True  # Accept meta-learned policies
    
    # Budget linkage
    budget_learning_link: bool = True  # Link budget to learning intensity
    min_budget_for_aggressive: float = 100.0  # Min budget for aggressive learning
    
    # Statistics
    total_runs: int = 0
    successful_runs: int = 0
    total_cost_spent: float = 0.0
    policy_updates_count: int = 0
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_learning_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "learning_enabled": self.learning_enabled,
            "intensity": self.intensity.value,
            "cold_start_strategy": self.cold_start_strategy.value,
            "share_patterns": self.share_patterns,
            "accept_meta_learning": self.accept_meta_learning,
            "budget_learning_link": self.budget_learning_link,
            "min_budget_for_aggressive": self.min_budget_for_aggressive,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "total_cost_spent": self.total_cost_spent,
            "policy_updates_count": self.policy_updates_count,
            "created_at": self.created_at,
            "last_learning_at": self.last_learning_at
        }


@dataclass
class TenantLocalKnowledge:
    """Tenant-specific learned knowledge"""
    tenant_id: str
    
    # Task type performance
    task_type_success_rates: Dict[str, float] = field(default_factory=dict)
    task_type_avg_costs: Dict[str, float] = field(default_factory=dict)
    task_type_avg_latencies: Dict[str, float] = field(default_factory=dict)
    
    # Agent performance
    agent_success_rates: Dict[str, float] = field(default_factory=dict)
    agent_avg_costs: Dict[str, float] = field(default_factory=dict)
    
    # Strategy performance
    strategy_rewards: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    # Learned preferences
    preferred_strategies: Dict[str, str] = field(default_factory=dict)  # task_type -> strategy
    preferred_agents: Dict[str, List[str]] = field(default_factory=dict)  # task_type -> agents
    
    # Custom thresholds (learned from experience)
    learned_cost_threshold: float = 1.0
    learned_latency_threshold_ms: int = 5000
    learned_quality_threshold: float = 0.7
    
    # Metadata
    sample_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "task_type_success_rates": self.task_type_success_rates,
            "task_type_avg_costs": self.task_type_avg_costs,
            "task_type_avg_latencies": self.task_type_avg_latencies,
            "agent_success_rates": self.agent_success_rates,
            "agent_avg_costs": self.agent_avg_costs,
            "strategy_rewards": {k: list(v) for k, v in self.strategy_rewards.items()},
            "preferred_strategies": self.preferred_strategies,
            "preferred_agents": self.preferred_agents,
            "learned_cost_threshold": self.learned_cost_threshold,
            "learned_latency_threshold_ms": self.learned_latency_threshold_ms,
            "learned_quality_threshold": self.learned_quality_threshold,
            "sample_count": self.sample_count,
            "last_updated": self.last_updated
        }


@dataclass
class CrossTenantPattern:
    """Anonymized pattern shared across tenants"""
    pattern_id: str
    pattern_type: str  # "task_strategy", "failure_signature", "success_recipe"
    
    # Pattern data (anonymized, no tenant-specific info)
    task_type: str
    strategy_id: str
    
    # Aggregated metrics
    avg_success_rate: float
    avg_cost: float
    avg_quality: float
    sample_count: int
    
    # Contributing tenants (count only, not IDs)
    contributing_tenant_count: int
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TenantLearningController:
    """
    Controller for tenant-level learning.
    
    Manages:
    - Tenant learning profiles
    - Local knowledge stores
    - Cross-tenant pattern aggregation
    - Cold-start initialization
    - Budget-learning linkage
    """
    
    def __init__(self, artifacts_dir: str = "artifacts/learning/tenants"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Tenant data stores
        self.profiles: Dict[str, TenantLearningProfile] = {}
        self.local_knowledge: Dict[str, TenantLocalKnowledge] = {}
        self.cross_tenant_patterns: Dict[str, CrossTenantPattern] = {}
        
        # Load existing data
        self._load_all()
    
    def initialize_tenant(
        self,
        tenant_id: str,
        budget: float = 0.0,
        cold_start_strategy: ColdStartStrategy = ColdStartStrategy.META_LEARNING
    ) -> TenantLearningProfile:
        """Initialize learning for a new tenant"""
        
        # Create profile
        profile = TenantLearningProfile(
            tenant_id=tenant_id,
            cold_start_strategy=cold_start_strategy,
            intensity=self._compute_initial_intensity(budget)
        )
        
        # Create local knowledge store
        knowledge = TenantLocalKnowledge(tenant_id=tenant_id)
        
        # Apply cold-start strategy
        self._apply_cold_start(profile, knowledge, budget)
        
        # Store
        self.profiles[tenant_id] = profile
        self.local_knowledge[tenant_id] = knowledge
        
        # Persist
        self._save_profile(profile)
        self._save_knowledge(knowledge)
        
        return profile
    
    def record_execution(
        self,
        tenant_id: str,
        task_type: str,
        strategy_id: str,
        agents_used: List[str],
        success: bool,
        cost: float,
        latency_ms: int,
        quality_score: float
    ):
        """Record an execution for tenant learning"""
        
        if tenant_id not in self.profiles:
            self.initialize_tenant(tenant_id)
        
        profile = self.profiles[tenant_id]
        knowledge = self.local_knowledge[tenant_id]
        
        if not profile.learning_enabled:
            return
        
        # Update profile statistics
        profile.total_runs += 1
        if success:
            profile.successful_runs += 1
        profile.total_cost_spent += cost
        
        # Update local knowledge
        self._update_local_knowledge(
            knowledge, task_type, strategy_id, agents_used,
            success, cost, latency_ms, quality_score
        )
        
        # Check if should contribute to cross-tenant patterns
        if profile.share_patterns:
            self._contribute_to_cross_tenant(
                task_type, strategy_id, success, cost, quality_score
            )
        
        # Persist
        self._save_profile(profile)
        self._save_knowledge(knowledge)
    
    def get_recommended_strategy(
        self,
        tenant_id: str,
        task_type: str
    ) -> Dict[str, Any]:
        """Get recommended strategy for a tenant and task type"""
        
        if tenant_id not in self.profiles:
            return self._get_default_recommendation(task_type)
        
        profile = self.profiles[tenant_id]
        knowledge = self.local_knowledge[tenant_id]
        
        # Check if tenant has enough data
        if knowledge.sample_count < 10:
            # Use cold-start strategy
            return self._get_cold_start_recommendation(
                profile, knowledge, task_type
            )
        
        # Use local knowledge
        preferred_strategy = knowledge.preferred_strategies.get(task_type)
        preferred_agents = knowledge.preferred_agents.get(task_type, [])
        
        # Calculate confidence
        task_samples = len(knowledge.strategy_rewards.get(task_type, []))
        confidence = min(1.0, task_samples / 50)
        
        if preferred_strategy:
            return {
                "strategy_id": preferred_strategy,
                "agents": preferred_agents,
                "thresholds": {
                    "max_cost": knowledge.learned_cost_threshold,
                    "max_latency_ms": knowledge.learned_latency_threshold_ms,
                    "min_quality": knowledge.learned_quality_threshold
                },
                "confidence": confidence,
                "source": "tenant_local"
            }
        
        # Fall back to cross-tenant patterns if accepted
        if profile.accept_meta_learning:
            return self._get_meta_recommendation(task_type)
        
        return self._get_default_recommendation(task_type)
    
    def adjust_learning_intensity(
        self,
        tenant_id: str,
        remaining_budget: float
    ):
        """Adjust learning intensity based on remaining budget"""
        
        if tenant_id not in self.profiles:
            return
        
        profile = self.profiles[tenant_id]
        
        if not profile.budget_learning_link:
            return
        
        # Determine intensity based on budget
        if remaining_budget <= 0:
            new_intensity = LearningIntensity.OFF
        elif remaining_budget < profile.min_budget_for_aggressive * 0.2:
            new_intensity = LearningIntensity.MINIMAL
        elif remaining_budget < profile.min_budget_for_aggressive:
            new_intensity = LearningIntensity.STANDARD
        else:
            new_intensity = LearningIntensity.AGGRESSIVE
        
        if profile.intensity != new_intensity:
            profile.intensity = new_intensity
            self._save_profile(profile)
    
    def get_learning_report(self, tenant_id: str) -> Dict[str, Any]:
        """Get learning report for a tenant"""
        
        if tenant_id not in self.profiles:
            return {"error": "Tenant not found"}
        
        profile = self.profiles[tenant_id]
        knowledge = self.local_knowledge[tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "profile": profile.to_dict(),
            "knowledge_summary": {
                "sample_count": knowledge.sample_count,
                "task_types_seen": list(knowledge.task_type_success_rates.keys()),
                "strategies_tried": list(knowledge.strategy_rewards.keys()),
                "avg_success_rate": sum(knowledge.task_type_success_rates.values()) / max(1, len(knowledge.task_type_success_rates)),
            },
            "cross_tenant_contribution": {
                "enabled": profile.share_patterns,
                "patterns_contributed": sum(1 for p in self.cross_tenant_patterns.values() if True)  # Simplified
            },
            "recommendations_available": len(knowledge.preferred_strategies),
            "generated_at": datetime.now().isoformat()
        }
    
    def _compute_initial_intensity(self, budget: float) -> LearningIntensity:
        """Compute initial learning intensity based on budget"""
        if budget <= 0:
            return LearningIntensity.MINIMAL
        elif budget < 50:
            return LearningIntensity.STANDARD
        else:
            return LearningIntensity.AGGRESSIVE
    
    def _apply_cold_start(
        self,
        profile: TenantLearningProfile,
        knowledge: TenantLocalKnowledge,
        budget: float
    ):
        """Apply cold-start strategy to initialize knowledge"""
        
        if profile.cold_start_strategy == ColdStartStrategy.DEFAULT:
            # Use system defaults
            knowledge.learned_cost_threshold = 1.0
            knowledge.learned_quality_threshold = 0.7
            
        elif profile.cold_start_strategy == ColdStartStrategy.META_LEARNING:
            # Use cross-tenant patterns
            for pattern_id, pattern in self.cross_tenant_patterns.items():
                if pattern.avg_success_rate > 0.7:
                    # Good pattern, adopt
                    task_type = pattern.task_type
                    knowledge.preferred_strategies[task_type] = pattern.strategy_id
                    knowledge.task_type_success_rates[task_type] = pattern.avg_success_rate
                    knowledge.task_type_avg_costs[task_type] = pattern.avg_cost
            
        elif profile.cold_start_strategy == ColdStartStrategy.CONSERVATIVE:
            # Very conservative settings
            knowledge.learned_cost_threshold = 0.5
            knowledge.learned_latency_threshold_ms = 3000
            knowledge.learned_quality_threshold = 0.8
            
        elif profile.cold_start_strategy == ColdStartStrategy.CLONE_SIMILAR:
            # Find similar tenant to clone from
            similar_tenant = self._find_similar_tenant(budget)
            if similar_tenant and similar_tenant in self.local_knowledge:
                source = self.local_knowledge[similar_tenant]
                knowledge.preferred_strategies = dict(source.preferred_strategies)
                knowledge.preferred_agents = dict(source.preferred_agents)
                knowledge.learned_cost_threshold = source.learned_cost_threshold
    
    def _update_local_knowledge(
        self,
        knowledge: TenantLocalKnowledge,
        task_type: str,
        strategy_id: str,
        agents_used: List[str],
        success: bool,
        cost: float,
        latency_ms: int,
        quality_score: float
    ):
        """Update local knowledge with new execution data"""
        
        knowledge.sample_count += 1
        knowledge.last_updated = datetime.now().isoformat()
        
        # Update task type statistics (exponential moving average)
        alpha = 0.1  # Learning rate
        
        if task_type not in knowledge.task_type_success_rates:
            knowledge.task_type_success_rates[task_type] = float(success)
            knowledge.task_type_avg_costs[task_type] = cost
            knowledge.task_type_avg_latencies[task_type] = float(latency_ms)
        else:
            old_rate = knowledge.task_type_success_rates[task_type]
            knowledge.task_type_success_rates[task_type] = (1 - alpha) * old_rate + alpha * float(success)
            
            old_cost = knowledge.task_type_avg_costs[task_type]
            knowledge.task_type_avg_costs[task_type] = (1 - alpha) * old_cost + alpha * cost
            
            old_lat = knowledge.task_type_avg_latencies[task_type]
            knowledge.task_type_avg_latencies[task_type] = (1 - alpha) * old_lat + alpha * float(latency_ms)
        
        # Update agent statistics
        for agent in agents_used:
            if agent not in knowledge.agent_success_rates:
                knowledge.agent_success_rates[agent] = float(success)
                knowledge.agent_avg_costs[agent] = cost / len(agents_used)
            else:
                old_rate = knowledge.agent_success_rates[agent]
                knowledge.agent_success_rates[agent] = (1 - alpha) * old_rate + alpha * float(success)
        
        # Update strategy rewards
        reward = self._compute_reward(success, cost, quality_score)
        knowledge.strategy_rewards[strategy_id].append(reward)
        
        # Update preferred strategy if this one is better
        current_preferred = knowledge.preferred_strategies.get(task_type)
        if current_preferred:
            current_rewards = knowledge.strategy_rewards.get(current_preferred, [0])
            new_rewards = knowledge.strategy_rewards.get(strategy_id, [0])
            if np.mean(new_rewards[-10:]) > np.mean(current_rewards[-10:]):
                knowledge.preferred_strategies[task_type] = strategy_id
                knowledge.preferred_agents[task_type] = agents_used
        else:
            knowledge.preferred_strategies[task_type] = strategy_id
            knowledge.preferred_agents[task_type] = agents_used
        
        # Update learned thresholds
        self._update_learned_thresholds(knowledge)
    
    def _compute_reward(
        self,
        success: bool,
        cost: float,
        quality: float
    ) -> float:
        """Compute reward from execution result"""
        base = 1.0 if success else 0.0
        quality_component = quality * 0.4
        cost_component = max(0, (1.0 - cost) * 0.2)
        return base * 0.4 + quality_component + cost_component
    
    def _update_learned_thresholds(self, knowledge: TenantLocalKnowledge):
        """Update learned thresholds based on experience"""
        
        if knowledge.sample_count < 20:
            return  # Not enough data
        
        # Cost threshold: 80th percentile of successful runs
        all_costs = list(knowledge.task_type_avg_costs.values())
        if all_costs:
            knowledge.learned_cost_threshold = np.percentile(all_costs, 80)
        
        # Latency threshold: 80th percentile
        all_latencies = list(knowledge.task_type_avg_latencies.values())
        if all_latencies:
            knowledge.learned_latency_threshold_ms = int(np.percentile(all_latencies, 80))
        
        # Quality threshold: based on success rate
        avg_success = np.mean(list(knowledge.task_type_success_rates.values()))
        knowledge.learned_quality_threshold = max(0.5, min(0.9, avg_success))
    
    def _contribute_to_cross_tenant(
        self,
        task_type: str,
        strategy_id: str,
        success: bool,
        cost: float,
        quality: float
    ):
        """Contribute anonymized pattern to cross-tenant knowledge"""
        
        pattern_id = f"{task_type}:{strategy_id}"
        
        if pattern_id not in self.cross_tenant_patterns:
            self.cross_tenant_patterns[pattern_id] = CrossTenantPattern(
                pattern_id=pattern_id,
                pattern_type="task_strategy",
                task_type=task_type,
                strategy_id=strategy_id,
                avg_success_rate=float(success),
                avg_cost=cost,
                avg_quality=quality,
                sample_count=1,
                contributing_tenant_count=1
            )
        else:
            pattern = self.cross_tenant_patterns[pattern_id]
            n = pattern.sample_count
            pattern.avg_success_rate = (pattern.avg_success_rate * n + float(success)) / (n + 1)
            pattern.avg_cost = (pattern.avg_cost * n + cost) / (n + 1)
            pattern.avg_quality = (pattern.avg_quality * n + quality) / (n + 1)
            pattern.sample_count += 1
            pattern.last_updated = datetime.now().isoformat()
        
        self._save_cross_tenant_patterns()
    
    def _get_default_recommendation(self, task_type: str) -> Dict[str, Any]:
        """Get default recommendation"""
        return {
            "strategy_id": "default_sequential",
            "agents": ["Product", "Data", "Execution", "Evaluation", "Cost"],
            "thresholds": {
                "max_cost": 1.0,
                "max_latency_ms": 5000,
                "min_quality": 0.7
            },
            "confidence": 0.0,
            "source": "system_default"
        }
    
    def _get_cold_start_recommendation(
        self,
        profile: TenantLearningProfile,
        knowledge: TenantLocalKnowledge,
        task_type: str
    ) -> Dict[str, Any]:
        """Get recommendation for cold-start tenant"""
        
        # Check if we have any cross-tenant data
        if profile.accept_meta_learning:
            for pattern_id, pattern in self.cross_tenant_patterns.items():
                if pattern.task_type == task_type and pattern.avg_success_rate > 0.6:
                    return {
                        "strategy_id": pattern.strategy_id,
                        "agents": ["Product", "Data", "Execution", "Evaluation", "Cost"],
                        "thresholds": {
                            "max_cost": pattern.avg_cost * 1.5,
                            "max_latency_ms": 5000,
                            "min_quality": min(0.9, pattern.avg_quality)
                        },
                        "confidence": min(0.8, pattern.sample_count / 100),
                        "source": "meta_learning"
                    }
        
        return self._get_default_recommendation(task_type)
    
    def _get_meta_recommendation(self, task_type: str) -> Dict[str, Any]:
        """Get recommendation from meta-learned patterns"""
        
        best_pattern = None
        best_score = 0.0
        
        for pattern in self.cross_tenant_patterns.values():
            if pattern.task_type == task_type:
                score = pattern.avg_success_rate * 0.5 + (1 - pattern.avg_cost) * 0.3 + pattern.avg_quality * 0.2
                if score > best_score:
                    best_score = score
                    best_pattern = pattern
        
        if best_pattern:
            return {
                "strategy_id": best_pattern.strategy_id,
                "agents": ["Product", "Data", "Execution", "Evaluation", "Cost"],
                "thresholds": {
                    "max_cost": best_pattern.avg_cost * 1.2,
                    "max_latency_ms": 5000,
                    "min_quality": best_pattern.avg_quality * 0.9
                },
                "confidence": min(0.9, best_pattern.sample_count / 200),
                "source": "cross_tenant_pattern"
            }
        
        return self._get_default_recommendation(task_type)
    
    def _find_similar_tenant(self, budget: float) -> Optional[str]:
        """Find a similar tenant based on budget"""
        
        similar_tenants = []
        for tenant_id, profile in self.profiles.items():
            # Simple similarity: similar budget level
            if self.local_knowledge[tenant_id].sample_count > 50:
                similar_tenants.append((tenant_id, profile.total_cost_spent))
        
        if not similar_tenants:
            return None
        
        # Find closest by total spend
        similar_tenants.sort(key=lambda x: abs(x[1] - budget))
        return similar_tenants[0][0]
    
    def _save_profile(self, profile: TenantLearningProfile):
        """Save tenant profile"""
        path = os.path.join(self.artifacts_dir, f"{profile.tenant_id}_profile.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_knowledge(self, knowledge: TenantLocalKnowledge):
        """Save tenant local knowledge"""
        path = os.path.join(self.artifacts_dir, f"{knowledge.tenant_id}_knowledge.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(knowledge.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_cross_tenant_patterns(self):
        """Save cross-tenant patterns"""
        path = os.path.join(self.artifacts_dir, "cross_tenant_patterns.json")
        patterns = {k: v.to_dict() for k, v in self.cross_tenant_patterns.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
    
    def _load_all(self):
        """Load all stored data"""
        
        if not os.path.exists(self.artifacts_dir):
            return
        
        # Load profiles and knowledge
        for filename in os.listdir(self.artifacts_dir):
            if filename.endswith("_profile.json"):
                tenant_id = filename.replace("_profile.json", "")
                path = os.path.join(self.artifacts_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.profiles[tenant_id] = TenantLearningProfile(
                        tenant_id=data["tenant_id"],
                        learning_enabled=data.get("learning_enabled", True),
                        intensity=LearningIntensity(data.get("intensity", "standard")),
                        cold_start_strategy=ColdStartStrategy(data.get("cold_start_strategy", "meta_learning")),
                        share_patterns=data.get("share_patterns", False),
                        accept_meta_learning=data.get("accept_meta_learning", True),
                        budget_learning_link=data.get("budget_learning_link", True),
                        min_budget_for_aggressive=data.get("min_budget_for_aggressive", 100.0),
                        total_runs=data.get("total_runs", 0),
                        successful_runs=data.get("successful_runs", 0),
                        total_cost_spent=data.get("total_cost_spent", 0.0),
                        policy_updates_count=data.get("policy_updates_count", 0),
                        created_at=data.get("created_at", ""),
                        last_learning_at=data.get("last_learning_at")
                    )
                except Exception:
                    pass
            
            elif filename.endswith("_knowledge.json"):
                tenant_id = filename.replace("_knowledge.json", "")
                path = os.path.join(self.artifacts_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.local_knowledge[tenant_id] = TenantLocalKnowledge(
                        tenant_id=data["tenant_id"],
                        task_type_success_rates=data.get("task_type_success_rates", {}),
                        task_type_avg_costs=data.get("task_type_avg_costs", {}),
                        task_type_avg_latencies=data.get("task_type_avg_latencies", {}),
                        agent_success_rates=data.get("agent_success_rates", {}),
                        agent_avg_costs=data.get("agent_avg_costs", {}),
                        strategy_rewards=defaultdict(list, {k: list(v) for k, v in data.get("strategy_rewards", {}).items()}),
                        preferred_strategies=data.get("preferred_strategies", {}),
                        preferred_agents=data.get("preferred_agents", {}),
                        learned_cost_threshold=data.get("learned_cost_threshold", 1.0),
                        learned_latency_threshold_ms=data.get("learned_latency_threshold_ms", 5000),
                        learned_quality_threshold=data.get("learned_quality_threshold", 0.7),
                        sample_count=data.get("sample_count", 0),
                        last_updated=data.get("last_updated", "")
                    )
                except Exception:
                    pass
        
        # Load cross-tenant patterns
        patterns_path = os.path.join(self.artifacts_dir, "cross_tenant_patterns.json")
        if os.path.exists(patterns_path):
            try:
                with open(patterns_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pattern_id, pattern_data in data.items():
                    self.cross_tenant_patterns[pattern_id] = CrossTenantPattern(**pattern_data)
            except Exception:
                pass


# Global tenant learning controller
_tenant_controller: Optional[TenantLearningController] = None

def get_tenant_learning_controller() -> TenantLearningController:
    """Get global tenant learning controller"""
    global _tenant_controller
    if _tenant_controller is None:
        _tenant_controller = TenantLearningController()
    return _tenant_controller


