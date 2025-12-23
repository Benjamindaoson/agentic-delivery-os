"""
Reward Model: Convert success criteria + optimization targets into reward signals.
L5-grade: All rewards are explicit, decomposable, artifact-driven.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field

from runtime.planning.goal_interpreter import Goal, SuccessCriterion, OptimizationTarget


@dataclass
class RewardComponent:
    """A single reward component."""
    component_id: str
    source: str  # criterion, optimization, penalty
    value: float
    weight: float
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RewardSignal:
    """Complete reward signal for a run."""
    run_id: str
    goal_id: str
    
    # Sparse reward (binary success)
    sparse_reward: float  # 0.0 or 1.0
    
    # Dense partial reward
    dense_reward: float  # 0.0-1.0, weighted sum
    
    # Decomposed components
    success_components: List[RewardComponent]
    optimization_components: List[RewardComponent]
    penalty_components: List[RewardComponent]
    
    # Totals
    total_reward: float
    total_penalty: float
    net_reward: float
    
    # Metadata
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal_id": self.goal_id,
            "sparse_reward": self.sparse_reward,
            "dense_reward": self.dense_reward,
            "success_components": [c.to_dict() for c in self.success_components],
            "optimization_components": [c.to_dict() for c in self.optimization_components],
            "penalty_components": [c.to_dict() for c in self.penalty_components],
            "total_reward": self.total_reward,
            "total_penalty": self.total_penalty,
            "net_reward": self.net_reward,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }


class RewardModel:
    """
    Computes reward signals from goal outcomes.
    
    Supports:
    - Sparse success reward (binary)
    - Dense partial reward (weighted components)
    - Penalty channels (cost, retries, hallucination risk)
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.rewards_dir = os.path.join(artifacts_dir, "rewards")
        os.makedirs(self.rewards_dir, exist_ok=True)
    
    def compute_reward(
        self,
        goal: Goal,
        outcome: Dict[str, Any],
        execution_metrics: Optional[Dict[str, Any]] = None
    ) -> RewardSignal:
        """
        Compute reward signal for a run outcome.
        
        Args:
            goal: The goal that was pursued
            outcome: The execution outcome
            execution_metrics: Optional execution metrics (cost, latency, retries)
            
        Returns:
            RewardSignal
        """
        execution_metrics = execution_metrics or {}
        
        # Compute success components
        success_components, sparse_reward = self._compute_success_reward(
            goal.success_criteria, outcome
        )
        
        # Compute optimization components
        optimization_components = self._compute_optimization_reward(
            goal.optimization_targets, outcome, execution_metrics
        )
        
        # Compute penalty components
        penalty_components = self._compute_penalties(execution_metrics)
        
        # Calculate totals
        total_success = sum(c.value * c.weight for c in success_components)
        total_optimization = sum(c.value * c.weight for c in optimization_components)
        total_penalty = sum(c.value * c.weight for c in penalty_components)
        
        # Normalize success weight
        success_weight_sum = sum(c.weight for c in success_components) or 1.0
        normalized_success = total_success / success_weight_sum
        
        # Dense reward: weighted combination
        dense_reward = 0.6 * normalized_success + 0.4 * total_optimization
        
        # Total reward and net
        total_reward = sparse_reward * 0.5 + dense_reward * 0.5
        net_reward = total_reward - total_penalty
        
        signal = RewardSignal(
            run_id=goal.run_id,
            goal_id=goal.goal_id,
            sparse_reward=sparse_reward,
            dense_reward=dense_reward,
            success_components=success_components,
            optimization_components=optimization_components,
            penalty_components=penalty_components,
            total_reward=round(total_reward, 4),
            total_penalty=round(total_penalty, 4),
            net_reward=round(net_reward, 4)
        )
        
        # Save artifact
        self._save_reward(signal)
        
        return signal
    
    def load_reward(self, run_id: str) -> Optional[RewardSignal]:
        """Load reward from artifact."""
        path = os.path.join(self.rewards_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_reward(data)
    
    def _compute_success_reward(
        self,
        criteria: List[SuccessCriterion],
        outcome: Dict[str, Any]
    ) -> tuple:
        """Compute success reward components."""
        components = []
        all_required_met = True
        
        for criterion in criteria:
            met, value = self._check_criterion(criterion, outcome)
            
            if criterion.required and not met:
                all_required_met = False
            
            components.append(RewardComponent(
                component_id=criterion.criterion_id,
                source="criterion",
                value=value,
                weight=criterion.weight,
                description=criterion.description,
                details={"met": met, "check_type": criterion.check_type}
            ))
        
        sparse_reward = 1.0 if all_required_met else 0.0
        
        return components, sparse_reward
    
    def _check_criterion(
        self,
        criterion: SuccessCriterion,
        outcome: Dict[str, Any]
    ) -> tuple:
        """Check if a criterion is met."""
        output = outcome.get("output", "")
        success = outcome.get("success", False)
        
        if criterion.check_type == "contains":
            keywords = criterion.check_value if isinstance(criterion.check_value, list) else [criterion.check_value]
            met = any(kw.lower() in output.lower() for kw in keywords if kw)
            return met, 1.0 if met else 0.0
        
        elif criterion.check_type == "threshold":
            if isinstance(criterion.check_value, dict):
                for key, threshold in criterion.check_value.items():
                    actual = outcome.get(key, 0)
                    if actual < threshold:
                        return False, actual / threshold if threshold > 0 else 0.0
                return True, 1.0
            return success, 1.0 if success else 0.0
        
        elif criterion.check_type == "exact":
            met = output == criterion.check_value
            return met, 1.0 if met else 0.0
        
        elif criterion.check_type == "regex":
            import re
            try:
                met = bool(re.search(criterion.check_value, output))
                return met, 1.0 if met else 0.0
            except re.error:
                return False, 0.0
        
        elif criterion.check_type == "schema":
            # Simplified schema check
            return success, 1.0 if success else 0.0
        
        elif criterion.check_type == "semantic":
            # Would require embedding comparison; simplified here
            return success, 1.0 if success else 0.5
        
        return success, 1.0 if success else 0.0
    
    def _compute_optimization_reward(
        self,
        targets: List[OptimizationTarget],
        outcome: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> List[RewardComponent]:
        """Compute optimization reward components."""
        components = []
        
        for target in targets:
            value = self._evaluate_target(target, outcome, metrics)
            
            components.append(RewardComponent(
                component_id=target.target_id,
                source="optimization",
                value=value,
                weight=target.weight,
                description=f"Optimize {target.dimension} ({target.direction})",
                details={"dimension": target.dimension, "direction": target.direction}
            ))
        
        return components
    
    def _evaluate_target(
        self,
        target: OptimizationTarget,
        outcome: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> float:
        """Evaluate an optimization target."""
        dimension = target.dimension
        direction = target.direction
        baseline = target.baseline
        
        # Get actual value
        if dimension == "quality":
            actual = outcome.get("quality_score", 0.8 if outcome.get("success") else 0.3)
        elif dimension == "cost":
            actual = metrics.get("cost", 0.0)
            # Invert for minimize (lower cost = higher reward)
            if direction == "minimize":
                max_cost = baseline or 1.0
                return max(0.0, 1.0 - actual / max_cost)
        elif dimension == "latency":
            actual = metrics.get("latency_ms", 0.0)
            if direction == "minimize":
                max_latency = baseline or 5000.0
                return max(0.0, 1.0 - actual / max_latency)
        elif dimension == "coverage":
            actual = metrics.get("coverage", outcome.get("evidence_count", 0) / 10)
            return min(1.0, actual)
        else:
            actual = 0.5
        
        return min(1.0, max(0.0, actual))
    
    def _compute_penalties(self, metrics: Dict[str, Any]) -> List[RewardComponent]:
        """Compute penalty components."""
        penalties = []
        
        # Cost penalty
        cost = metrics.get("cost", 0.0)
        if cost > 0:
            cost_penalty = min(0.3, cost * 0.5)  # Cap at 0.3
            penalties.append(RewardComponent(
                component_id="cost_penalty",
                source="penalty",
                value=cost_penalty,
                weight=1.0,
                description="Cost penalty",
                details={"cost": cost}
            ))
        
        # Retry penalty
        retries = metrics.get("retries", 0)
        if retries > 0:
            retry_penalty = min(0.2, retries * 0.05)  # 5% per retry, cap 20%
            penalties.append(RewardComponent(
                component_id="retry_penalty",
                source="penalty",
                value=retry_penalty,
                weight=1.0,
                description="Retry penalty",
                details={"retries": retries}
            ))
        
        # Hallucination risk penalty
        hallucination_risk = metrics.get("hallucination_risk", 0.0)
        if hallucination_risk > 0:
            penalties.append(RewardComponent(
                component_id="hallucination_penalty",
                source="penalty",
                value=hallucination_risk * 0.4,
                weight=1.0,
                description="Hallucination risk penalty",
                details={"risk": hallucination_risk}
            ))
        
        # Latency penalty (if exceeds threshold)
        latency = metrics.get("latency_ms", 0)
        latency_threshold = metrics.get("latency_threshold_ms", 5000)
        if latency > latency_threshold:
            excess_ratio = (latency - latency_threshold) / latency_threshold
            latency_penalty = min(0.2, excess_ratio * 0.1)
            penalties.append(RewardComponent(
                component_id="latency_penalty",
                source="penalty",
                value=latency_penalty,
                weight=1.0,
                description="Latency exceeded threshold",
                details={"latency_ms": latency, "threshold_ms": latency_threshold}
            ))
        
        return penalties
    
    def _save_reward(self, signal: RewardSignal) -> None:
        """Save reward to artifact."""
        path = os.path.join(self.rewards_dir, f"{signal.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(signal.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_reward(self, data: Dict[str, Any]) -> RewardSignal:
        """Convert dict to RewardSignal."""
        return RewardSignal(
            run_id=data["run_id"],
            goal_id=data["goal_id"],
            sparse_reward=data["sparse_reward"],
            dense_reward=data["dense_reward"],
            success_components=[
                RewardComponent(**c) for c in data["success_components"]
            ],
            optimization_components=[
                RewardComponent(**c) for c in data["optimization_components"]
            ],
            penalty_components=[
                RewardComponent(**c) for c in data["penalty_components"]
            ],
            total_reward=data["total_reward"],
            total_penalty=data["total_penalty"],
            net_reward=data["net_reward"],
            created_at=data.get("created_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



