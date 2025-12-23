"""
Unified Policy Abstraction: Common interface for Bandit, RL, and Meta-Policy
P3 Implementation: Unified state/action/reward interface with paradigm migration

This module provides:
1. Unified AbstractPolicy interface
2. State/Action/Reward definitions
3. Paradigm migration between Bandit/RL/Meta
4. Task success semantics for reward
5. Explainable, traceable rewards
"""

import os
import json
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Generic, TypeVar
from dataclasses import dataclass, field, asdict
from enum import Enum


# ============================================================================
# Core Abstractions
# ============================================================================

class PolicyParadigm(str, Enum):
    """Policy learning paradigms"""
    BANDIT = "bandit"              # Multi-armed bandit
    CONTEXTUAL_BANDIT = "contextual_bandit"  # Contextual bandit
    OFFLINE_RL = "offline_rl"      # Offline reinforcement learning
    META_LEARNING = "meta_learning"  # Meta-learning across contexts


@dataclass
class State:
    """Unified state representation"""
    state_id: str
    
    # Task context
    task_type: str
    task_complexity: str
    query_features: Dict[str, float] = field(default_factory=dict)
    
    # Historical context
    recent_success_rate: float = 0.5
    recent_avg_cost: float = 0.5
    recent_avg_latency_ms: int = 2000
    
    # Constraint context
    remaining_budget: float = 1.0
    time_of_day_normalized: float = 0.5
    
    # User/tenant context
    tenant_id: Optional[str] = None
    user_preference_embedding: Optional[List[float]] = None
    
    def to_vector(self, dim: int = 20) -> np.ndarray:
        """Convert state to fixed-dimension vector"""
        vec = np.zeros(dim)
        
        # Task type encoding (first 5 dims)
        task_types = ["retrieve", "analyze", "build", "qa", "summarize"]
        if self.task_type in task_types:
            vec[task_types.index(self.task_type)] = 1.0
        
        # Complexity encoding (dims 5-8)
        complexity_map = {"trivial": 0, "simple": 1, "moderate": 2, "complex": 3, "expert": 4}
        if self.task_complexity in complexity_map:
            idx = 5 + complexity_map[self.task_complexity]
            vec[min(idx, 8)] = 1.0
        
        # Historical metrics (dims 9-11)
        vec[9] = self.recent_success_rate
        vec[10] = min(1.0, self.recent_avg_cost)
        vec[11] = min(1.0, self.recent_avg_latency_ms / 10000)
        
        # Constraints (dims 12-13)
        vec[12] = self.remaining_budget
        vec[13] = self.time_of_day_normalized
        
        # Query features (dims 14-19)
        for i, (k, v) in enumerate(list(self.query_features.items())[:6]):
            vec[14 + i] = v
        
        return vec
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Action:
    """Unified action representation"""
    action_id: str
    
    # Strategy selection
    strategy_id: str
    
    # Component selections
    planner_mode: str = "sequential"
    retrieval_policy: str = "semantic"
    generation_config: Dict[str, Any] = field(default_factory=dict)
    agent_toggles: Dict[str, bool] = field(default_factory=dict)
    
    # Resource allocations
    cost_budget: float = 1.0
    latency_budget_ms: int = 5000
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_index(self, action_space: List[str]) -> int:
        """Convert to action index for discrete algorithms"""
        if self.strategy_id in action_space:
            return action_space.index(self.strategy_id)
        return 0


@dataclass
class Reward:
    """Unified reward with semantic task success"""
    reward_id: str
    
    # Component rewards
    task_success: float          # 0 or 1 (hard success/failure)
    quality_score: float         # 0-1 continuous quality
    user_satisfaction_proxy: float  # Estimated user satisfaction
    
    # Efficiency rewards
    cost_efficiency: float       # 1 - (cost / budget)
    latency_efficiency: float    # 1 - (latency / target)
    
    # Combined reward
    total_reward: float
    
    # Attribution (traceable)
    contributing_factors: Dict[str, float] = field(default_factory=dict)
    reward_rationale: str = ""
    
    # Metadata
    state_id: str = ""
    action_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Reward Computer with Task Success Semantics
# ============================================================================

class TaskSuccessRewardComputer:
    """
    Computes rewards with explicit task success semantics.
    
    Reward = w1*task_success + w2*quality + w3*user_satisfaction + w4*cost_efficiency + w5*latency_efficiency
    
    All components are traceable and explainable.
    """
    
    def __init__(
        self,
        task_success_weight: float = 0.35,
        quality_weight: float = 0.25,
        satisfaction_weight: float = 0.15,
        cost_weight: float = 0.15,
        latency_weight: float = 0.10
    ):
        self.weights = {
            "task_success": task_success_weight,
            "quality": quality_weight,
            "satisfaction": satisfaction_weight,
            "cost": cost_weight,
            "latency": latency_weight
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
    
    def compute(
        self,
        state: State,
        action: Action,
        outcome: Dict[str, Any]
    ) -> Reward:
        """Compute reward from execution outcome"""
        
        # Extract components
        task_success = 1.0 if outcome.get("success", False) else 0.0
        quality_score = outcome.get("quality_score", 0.5)
        
        # User satisfaction proxy (combine multiple signals)
        user_satisfaction = self._estimate_user_satisfaction(outcome)
        
        # Cost efficiency
        actual_cost = outcome.get("cost", 0.0)
        cost_budget = action.cost_budget
        cost_efficiency = max(0.0, 1.0 - (actual_cost / cost_budget)) if cost_budget > 0 else 0.5
        
        # Latency efficiency
        actual_latency = outcome.get("latency_ms", 0)
        latency_budget = action.latency_budget_ms
        latency_efficiency = max(0.0, 1.0 - (actual_latency / latency_budget)) if latency_budget > 0 else 0.5
        
        # Compute weighted total
        total_reward = (
            self.weights["task_success"] * task_success +
            self.weights["quality"] * quality_score +
            self.weights["satisfaction"] * user_satisfaction +
            self.weights["cost"] * cost_efficiency +
            self.weights["latency"] * latency_efficiency
        )
        
        # Build contributing factors
        contributing_factors = {
            "task_success": task_success * self.weights["task_success"],
            "quality_score": quality_score * self.weights["quality"],
            "user_satisfaction": user_satisfaction * self.weights["satisfaction"],
            "cost_efficiency": cost_efficiency * self.weights["cost"],
            "latency_efficiency": latency_efficiency * self.weights["latency"]
        }
        
        # Generate rationale
        rationale = self._generate_rationale(
            task_success, quality_score, user_satisfaction,
            cost_efficiency, latency_efficiency, total_reward
        )
        
        return Reward(
            reward_id=f"reward_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            task_success=task_success,
            quality_score=quality_score,
            user_satisfaction_proxy=user_satisfaction,
            cost_efficiency=cost_efficiency,
            latency_efficiency=latency_efficiency,
            total_reward=total_reward,
            contributing_factors=contributing_factors,
            reward_rationale=rationale,
            state_id=state.state_id,
            action_id=action.action_id
        )
    
    def _estimate_user_satisfaction(self, outcome: Dict[str, Any]) -> float:
        """Estimate user satisfaction from outcome signals"""
        
        # Explicit feedback (if available)
        if "user_rating" in outcome:
            return outcome["user_rating"] / 5.0  # Assume 1-5 scale
        
        # Implicit signals
        satisfaction = 0.5  # Neutral default
        
        # Task success is a strong signal
        if outcome.get("success", False):
            satisfaction += 0.2
        else:
            satisfaction -= 0.2
        
        # Response quality
        quality = outcome.get("quality_score", 0.5)
        satisfaction += (quality - 0.5) * 0.3
        
        # Response time (users prefer faster)
        latency = outcome.get("latency_ms", 5000)
        if latency < 2000:
            satisfaction += 0.1
        elif latency > 10000:
            satisfaction -= 0.1
        
        return max(0.0, min(1.0, satisfaction))
    
    def _generate_rationale(
        self,
        task_success: float,
        quality: float,
        satisfaction: float,
        cost_eff: float,
        latency_eff: float,
        total: float
    ) -> str:
        """Generate human-readable reward rationale"""
        
        parts = []
        
        if task_success > 0.5:
            parts.append("Task completed successfully (+{:.2f})".format(
                task_success * self.weights["task_success"]))
        else:
            parts.append("Task failed (-{:.2f})".format(
                (1-task_success) * self.weights["task_success"]))
        
        if quality > 0.7:
            parts.append("High quality output (+{:.2f})".format(
                quality * self.weights["quality"]))
        elif quality < 0.4:
            parts.append("Low quality output (-{:.2f})".format(
                (1-quality) * self.weights["quality"]))
        
        if cost_eff > 0.7:
            parts.append("Good cost efficiency")
        elif cost_eff < 0.3:
            parts.append("Poor cost efficiency")
        
        rationale = "; ".join(parts)
        rationale += f" | Total reward: {total:.3f}"
        
        return rationale


# ============================================================================
# Abstract Policy Interface
# ============================================================================

class AbstractPolicy(ABC):
    """
    Unified policy interface for all learning paradigms.
    
    All policy implementations (Bandit, RL, Meta) should inherit from this.
    """
    
    def __init__(
        self,
        policy_id: str,
        paradigm: PolicyParadigm,
        action_space: List[str],
        artifacts_dir: str = "artifacts/policies"
    ):
        self.policy_id = policy_id
        self.paradigm = paradigm
        self.action_space = action_space
        self.artifacts_dir = artifacts_dir
        
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Statistics
        self.total_selections = 0
        self.total_reward = 0.0
        self.action_counts: Dict[str, int] = {a: 0 for a in action_space}
        self.action_rewards: Dict[str, List[float]] = {a: [] for a in action_space}
    
    @abstractmethod
    def select_action(self, state: State) -> Action:
        """Select action given current state"""
        pass
    
    @abstractmethod
    def update(self, state: State, action: Action, reward: Reward):
        """Update policy based on observed reward"""
        pass
    
    @abstractmethod
    def get_policy_state(self) -> Dict[str, Any]:
        """Get current policy state for serialization"""
        pass
    
    @abstractmethod
    def load_policy_state(self, state: Dict[str, Any]):
        """Load policy state from serialization"""
        pass
    
    def record_selection(self, action: Action, reward: Reward):
        """Record action selection and reward"""
        self.total_selections += 1
        self.total_reward += reward.total_reward
        self.action_counts[action.strategy_id] = self.action_counts.get(action.strategy_id, 0) + 1
        if action.strategy_id not in self.action_rewards:
            self.action_rewards[action.strategy_id] = []
        self.action_rewards[action.strategy_id].append(reward.total_reward)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get policy statistics"""
        return {
            "policy_id": self.policy_id,
            "paradigm": self.paradigm.value,
            "total_selections": self.total_selections,
            "avg_reward": self.total_reward / max(1, self.total_selections),
            "action_distribution": {
                a: c / max(1, self.total_selections)
                for a, c in self.action_counts.items()
            },
            "action_avg_rewards": {
                a: np.mean(rewards) if rewards else 0.0
                for a, rewards in self.action_rewards.items()
            }
        }
    
    def save(self):
        """Save policy to disk"""
        state = self.get_policy_state()
        state["statistics"] = self.get_statistics()
        state["saved_at"] = datetime.now().isoformat()
        
        path = os.path.join(self.artifacts_dir, f"{self.policy_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def load(self):
        """Load policy from disk"""
        path = os.path.join(self.artifacts_dir, f"{self.policy_id}.json")
        if not os.path.exists(path):
            return
        
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        self.load_policy_state(state)
        
        # Restore statistics
        stats = state.get("statistics", {})
        self.total_selections = stats.get("total_selections", 0)
        self.total_reward = stats.get("avg_reward", 0.0) * self.total_selections


# ============================================================================
# Concrete Policy Implementations
# ============================================================================

class UnifiedBanditPolicy(AbstractPolicy):
    """Unified bandit policy with UCB1"""
    
    def __init__(
        self,
        policy_id: str,
        action_space: List[str],
        exploration_rate: float = 1.0,
        artifacts_dir: str = "artifacts/policies"
    ):
        super().__init__(policy_id, PolicyParadigm.BANDIT, action_space, artifacts_dir)
        self.exploration_rate = exploration_rate
        
        # Bandit state
        self.q_values: Dict[str, float] = {a: 0.0 for a in action_space}
        self.action_counts_internal: Dict[str, int] = {a: 0 for a in action_space}
    
    def select_action(self, state: State) -> Action:
        """Select action using UCB1"""
        total = sum(self.action_counts_internal.values())
        
        if total == 0:
            # Random selection
            strategy_id = np.random.choice(self.action_space)
        else:
            # UCB1
            ucb_values = {}
            for action_id in self.action_space:
                n_a = self.action_counts_internal[action_id]
                if n_a == 0:
                    ucb_values[action_id] = float('inf')
                else:
                    q = self.q_values[action_id]
                    exploration = self.exploration_rate * np.sqrt(2 * np.log(total) / n_a)
                    ucb_values[action_id] = q + exploration
            
            strategy_id = max(ucb_values, key=ucb_values.get)
        
        return Action(
            action_id=f"action_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            strategy_id=strategy_id
        )
    
    def update(self, state: State, action: Action, reward: Reward):
        """Update Q-values"""
        strategy_id = action.strategy_id
        
        self.action_counts_internal[strategy_id] = self.action_counts_internal.get(strategy_id, 0) + 1
        n = self.action_counts_internal[strategy_id]
        
        # Incremental mean update
        old_q = self.q_values.get(strategy_id, 0.0)
        self.q_values[strategy_id] = old_q + (reward.total_reward - old_q) / n
        
        self.record_selection(action, reward)
    
    def get_policy_state(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "paradigm": self.paradigm.value,
            "action_space": self.action_space,
            "exploration_rate": self.exploration_rate,
            "q_values": self.q_values,
            "action_counts": self.action_counts_internal
        }
    
    def load_policy_state(self, state: Dict[str, Any]):
        self.q_values = state.get("q_values", self.q_values)
        self.action_counts_internal = state.get("action_counts", self.action_counts_internal)
        self.exploration_rate = state.get("exploration_rate", self.exploration_rate)


class UnifiedContextualBanditPolicy(AbstractPolicy):
    """Unified contextual bandit with linear UCB"""
    
    def __init__(
        self,
        policy_id: str,
        action_space: List[str],
        context_dim: int = 20,
        alpha: float = 1.0,
        artifacts_dir: str = "artifacts/policies"
    ):
        super().__init__(policy_id, PolicyParadigm.CONTEXTUAL_BANDIT, action_space, artifacts_dir)
        self.context_dim = context_dim
        self.alpha = alpha
        
        # LinUCB parameters
        self.A: Dict[str, np.ndarray] = {
            a: np.eye(context_dim) for a in action_space
        }
        self.b: Dict[str, np.ndarray] = {
            a: np.zeros(context_dim) for a in action_space
        }
    
    def select_action(self, state: State) -> Action:
        """Select action using LinUCB"""
        context = state.to_vector(self.context_dim)
        
        ucb_values = {}
        for action_id in self.action_space:
            A_inv = np.linalg.inv(self.A[action_id])
            theta = A_inv @ self.b[action_id]
            
            # Expected reward
            expected = context @ theta
            
            # Confidence bound
            confidence = self.alpha * np.sqrt(context @ A_inv @ context)
            
            ucb_values[action_id] = expected + confidence
        
        strategy_id = max(ucb_values, key=ucb_values.get)
        
        return Action(
            action_id=f"action_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            strategy_id=strategy_id
        )
    
    def update(self, state: State, action: Action, reward: Reward):
        """Update LinUCB parameters"""
        context = state.to_vector(self.context_dim)
        strategy_id = action.strategy_id
        
        self.A[strategy_id] += np.outer(context, context)
        self.b[strategy_id] += reward.total_reward * context
        
        self.record_selection(action, reward)
    
    def get_policy_state(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "paradigm": self.paradigm.value,
            "action_space": self.action_space,
            "context_dim": self.context_dim,
            "alpha": self.alpha,
            "A": {k: v.tolist() for k, v in self.A.items()},
            "b": {k: v.tolist() for k, v in self.b.items()}
        }
    
    def load_policy_state(self, state: Dict[str, Any]):
        self.alpha = state.get("alpha", self.alpha)
        if "A" in state:
            self.A = {k: np.array(v) for k, v in state["A"].items()}
        if "b" in state:
            self.b = {k: np.array(v) for k, v in state["b"].items()}


class UnifiedRLPolicy(AbstractPolicy):
    """Unified offline RL policy with Conservative Q-Learning"""
    
    def __init__(
        self,
        policy_id: str,
        action_space: List[str],
        state_dim: int = 20,
        learning_rate: float = 0.001,
        discount: float = 0.99,
        conservative_weight: float = 0.1,
        artifacts_dir: str = "artifacts/policies"
    ):
        super().__init__(policy_id, PolicyParadigm.OFFLINE_RL, action_space, artifacts_dir)
        self.state_dim = state_dim
        self.learning_rate = learning_rate
        self.discount = discount
        self.conservative_weight = conservative_weight
        
        # Simple Q-table (for discrete states, would use neural network for continuous)
        self.q_values: Dict[str, float] = {a: 0.0 for a in action_space}
        
        # Replay buffer
        self.replay_buffer: List[Tuple[np.ndarray, str, float, np.ndarray]] = []
        self.buffer_size = 10000
    
    def select_action(self, state: State) -> Action:
        """Select action (greedy in offline RL)"""
        strategy_id = max(self.q_values, key=self.q_values.get)
        
        return Action(
            action_id=f"action_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            strategy_id=strategy_id
        )
    
    def update(self, state: State, action: Action, reward: Reward):
        """Add to replay buffer (offline RL updates in batch)"""
        context = state.to_vector(self.state_dim)
        
        # Simplified: treat as bandit update
        old_q = self.q_values.get(action.strategy_id, 0.0)
        
        # Conservative update (penalize OOD)
        conservative_penalty = self.conservative_weight
        target = reward.total_reward - conservative_penalty
        
        self.q_values[action.strategy_id] = (1 - self.learning_rate) * old_q + self.learning_rate * target
        
        self.record_selection(action, reward)
    
    def get_policy_state(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "paradigm": self.paradigm.value,
            "action_space": self.action_space,
            "state_dim": self.state_dim,
            "learning_rate": self.learning_rate,
            "discount": self.discount,
            "conservative_weight": self.conservative_weight,
            "q_values": self.q_values
        }
    
    def load_policy_state(self, state: Dict[str, Any]):
        self.learning_rate = state.get("learning_rate", self.learning_rate)
        self.discount = state.get("discount", self.discount)
        self.conservative_weight = state.get("conservative_weight", self.conservative_weight)
        self.q_values = state.get("q_values", self.q_values)


# ============================================================================
# Paradigm Migration
# ============================================================================

class PolicyMigrator:
    """Migrates policies between paradigms"""
    
    @staticmethod
    def migrate(
        source_policy: AbstractPolicy,
        target_paradigm: PolicyParadigm,
        artifacts_dir: str = "artifacts/policies"
    ) -> AbstractPolicy:
        """
        Migrate policy from one paradigm to another.
        
        Preserves learned action preferences while adapting to new paradigm.
        """
        action_space = source_policy.action_space
        stats = source_policy.get_statistics()
        
        # Extract action preferences from source
        action_avg_rewards = stats.get("action_avg_rewards", {})
        
        # Create target policy
        new_policy_id = f"{source_policy.policy_id}_migrated_{target_paradigm.value}"
        
        if target_paradigm == PolicyParadigm.BANDIT:
            target = UnifiedBanditPolicy(
                policy_id=new_policy_id,
                action_space=action_space,
                artifacts_dir=artifacts_dir
            )
            # Initialize Q-values from source
            target.q_values = dict(action_avg_rewards)
            
        elif target_paradigm == PolicyParadigm.CONTEXTUAL_BANDIT:
            target = UnifiedContextualBanditPolicy(
                policy_id=new_policy_id,
                action_space=action_space,
                artifacts_dir=artifacts_dir
            )
            # Initialize b vectors to bias toward good actions
            for action_id, avg_reward in action_avg_rewards.items():
                target.b[action_id] = np.ones(target.context_dim) * avg_reward
            
        elif target_paradigm == PolicyParadigm.OFFLINE_RL:
            target = UnifiedRLPolicy(
                policy_id=new_policy_id,
                action_space=action_space,
                artifacts_dir=artifacts_dir
            )
            # Initialize Q-values from source
            target.q_values = dict(action_avg_rewards)
        
        else:
            raise ValueError(f"Unsupported target paradigm: {target_paradigm}")
        
        # Copy statistics
        target.total_selections = source_policy.total_selections
        target.total_reward = source_policy.total_reward
        target.action_counts = dict(source_policy.action_counts)
        target.action_rewards = {k: list(v) for k, v in source_policy.action_rewards.items()}
        
        return target


# ============================================================================
# Policy Factory
# ============================================================================

class PolicyFactory:
    """Factory for creating unified policies"""
    
    @staticmethod
    def create(
        paradigm: PolicyParadigm,
        policy_id: str,
        action_space: List[str],
        **kwargs
    ) -> AbstractPolicy:
        """Create policy of specified paradigm"""
        
        if paradigm == PolicyParadigm.BANDIT:
            return UnifiedBanditPolicy(
                policy_id=policy_id,
                action_space=action_space,
                exploration_rate=kwargs.get("exploration_rate", 1.0),
                artifacts_dir=kwargs.get("artifacts_dir", "artifacts/policies")
            )
        
        elif paradigm == PolicyParadigm.CONTEXTUAL_BANDIT:
            return UnifiedContextualBanditPolicy(
                policy_id=policy_id,
                action_space=action_space,
                context_dim=kwargs.get("context_dim", 20),
                alpha=kwargs.get("alpha", 1.0),
                artifacts_dir=kwargs.get("artifacts_dir", "artifacts/policies")
            )
        
        elif paradigm == PolicyParadigm.OFFLINE_RL:
            return UnifiedRLPolicy(
                policy_id=policy_id,
                action_space=action_space,
                state_dim=kwargs.get("state_dim", 20),
                learning_rate=kwargs.get("learning_rate", 0.001),
                discount=kwargs.get("discount", 0.99),
                conservative_weight=kwargs.get("conservative_weight", 0.1),
                artifacts_dir=kwargs.get("artifacts_dir", "artifacts/policies")
            )
        
        else:
            raise ValueError(f"Unsupported paradigm: {paradigm}")
    
    @staticmethod
    def load(
        policy_id: str,
        artifacts_dir: str = "artifacts/policies"
    ) -> Optional[AbstractPolicy]:
        """Load policy from disk"""
        path = os.path.join(artifacts_dir, f"{policy_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        paradigm = PolicyParadigm(state["paradigm"])
        action_space = state["action_space"]
        
        policy = PolicyFactory.create(paradigm, policy_id, action_space, artifacts_dir=artifacts_dir)
        policy.load_policy_state(state)
        
        return policy


