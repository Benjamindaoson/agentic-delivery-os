"""
Bandit Selector - Multi-armed bandit for strategy selection
Upgraded to implement AbstractPolicy for unified learning interface.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import os
import random
import math

from learning.abstract_policy import AbstractPolicy
from learning.semantic_task_success import compute_semantic_reward


class BanditArm(BaseModel):
    """Single arm in multi-armed bandit"""
    arm_id: str
    pulls: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    confidence: float = 0.0


class BanditState(BaseModel):
    """State of the bandit selector"""
    total_pulls: int = 0
    arms: Dict[str, BanditArm]
    exploration_rate: float = 0.1
    algorithm: str = "ucb1"  # ucb1 | thompson | epsilon_greedy


class BanditSelector(AbstractPolicy):
    """
    Multi-armed bandit for intelligent strategy selection.
    Implements AbstractPolicy for interoperability (Bandit -> RL migration).
    """

    policy_id = "bandit_selector"
    version = "1.0"

    def __init__(
        self,
        state_path: str = "artifacts/learning/bandit_state.json",
        algorithm: str = "ucb1",
        exploration_rate: float = 0.1,
    ):
        self.state_path = state_path
        self.algorithm = algorithm
        self.exploration_rate = exploration_rate

        # Load or initialize state
        self.state = self._load_state()
    
    def _load_state(self) -> BanditState:
        """Load bandit state from disk"""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                data = json.load(f)
                return BanditState(**data)
        
        return BanditState(
            total_pulls=0,
            arms={},
            exploration_rate=self.exploration_rate,
            algorithm=self.algorithm
        )
    
    def register_arm(self, arm_id: str):
        """Register a new strategy arm"""
        if arm_id not in self.state.arms:
            self.state.arms[arm_id] = BanditArm(arm_id=arm_id)
            self._save_state()
    
    def select_arm(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Select an arm to pull
        Args:
            context: Optional context for contextual bandits
        Returns:
            Selected arm_id
        """
        if not self.state.arms:
            raise ValueError("No arms registered")
        
        # Select based on algorithm
        if self.algorithm == "ucb1":
            return self._select_ucb1()
        elif self.algorithm == "epsilon_greedy":
            return self._select_epsilon_greedy()
        elif self.algorithm == "thompson":
            return self._select_thompson()
        else:
            # Default: random
            return random.choice(list(self.state.arms.keys()))
    
    def update_reward(self, arm_id: str, reward: float):
        """
        Update arm with observed reward
        Args:
            arm_id: Arm that was pulled
            reward: Reward received (0-1)
        """
        if arm_id not in self.state.arms:
            raise ValueError(f"Unknown arm: {arm_id}")
        
        arm = self.state.arms[arm_id]
        
        # Update arm statistics
        arm.pulls += 1
        arm.total_reward += reward
        arm.avg_reward = arm.total_reward / arm.pulls
        
        # Update confidence (UCB)
        arm.confidence = self._compute_confidence(arm)
        
        # Update global state
        self.state.total_pulls += 1
        
        # Save state
        self._save_state()
    
    def _select_ucb1(self) -> str:
        """UCB1 algorithm selection"""
        if self.state.total_pulls == 0:
            # Pull each arm once initially
            for arm_id, arm in self.state.arms.items():
                if arm.pulls == 0:
                    return arm_id
        
        # Select arm with highest UCB score
        best_arm = None
        best_score = float('-inf')
        
        for arm_id, arm in self.state.arms.items():
            if arm.pulls == 0:
                return arm_id  # Unexplored arms have highest priority
            
            # UCB1 score: avg_reward + sqrt(2 * ln(total_pulls) / arm_pulls)
            exploration_bonus = math.sqrt(2 * math.log(self.state.total_pulls) / arm.pulls)
            ucb_score = arm.avg_reward + exploration_bonus
            
            if ucb_score > best_score:
                best_score = ucb_score
                best_arm = arm_id
        
        return best_arm if best_arm else random.choice(list(self.state.arms.keys()))
    
    def _select_epsilon_greedy(self) -> str:
        """Epsilon-greedy selection"""
        # Explore with probability epsilon
        if random.random() < self.state.exploration_rate:
            return random.choice(list(self.state.arms.keys()))
        
        # Exploit: select best arm
        best_arm = max(
            self.state.arms.items(),
            key=lambda x: x[1].avg_reward
        )
        return best_arm[0]
    
    def _select_thompson(self) -> str:
        """Thompson sampling selection (simplified Beta distribution)"""
        # Simplified: sample from distribution proportional to avg_reward
        arms_list = list(self.state.arms.items())
        
        # Add small constant to avoid zero probabilities
        weights = [arm.avg_reward + 0.01 for _, arm in arms_list]
        
        # Normalize to probabilities
        total = sum(weights)
        probs = [w / total for w in weights]
        
        # Sample
        selected_idx = random.choices(range(len(arms_list)), weights=probs)[0]
        return arms_list[selected_idx][0]
    
    def _compute_confidence(self, arm: BanditArm) -> float:
        """Compute confidence interval width"""
        if arm.pulls == 0:
            return 1.0
        
        # Simple confidence based on sample size
        return 1.0 / math.sqrt(arm.pulls)
    
    def _save_state(self):
        """Persist bandit state"""
        with open(self.state_path, 'w') as f:
            f.write(self.state.model_dump_json(indent=2))
    
    def get_best_arm(self) -> str:
        """Get current best performing arm"""
        if not self.state.arms:
            raise ValueError("No arms registered")
        
        best_arm = max(
            self.state.arms.items(),
            key=lambda x: x[1].avg_reward
        )
        return best_arm[0]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bandit statistics"""
        return {
            "total_pulls": self.state.total_pulls,
            "num_arms": len(self.state.arms),
            "algorithm": self.algorithm,
            "exploration_rate": self.state.exploration_rate,
            "arm_stats": {
                arm_id: {
                    "pulls": arm.pulls,
                    "avg_reward": arm.avg_reward,
                    "confidence": arm.confidence
                }
                for arm_id, arm in self.state.arms.items()
            },
            "best_arm": self.get_best_arm() if self.state.arms else None
        }
    
    def reset(self):
        """Reset bandit state"""
        self.state = BanditState(
            total_pulls=0,
            arms={arm_id: BanditArm(arm_id=arm_id) for arm_id in self.state.arms.keys()},
            exploration_rate=self.exploration_rate,
            algorithm=self.algorithm
        )
        self._save_state()

    # ==== AbstractPolicy interface ====
    def encode_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Bandit uses lightweight context; return as-is."""
        return context or {}

    def select_action(self, state: Dict[str, Any], **kwargs) -> str:
        """Alias to select_arm."""
        return self.select_arm(state)

    def compute_reward(self, outcome: Dict[str, Any], task_id: Optional[str] = None, **kwargs) -> float:
        """
        Compute semantic reward for bandit using unified reward model.
        Expects outcome to contain quality_score, grounding_score, cost_efficiency, user_intent_match.
        """
        reward, _ = compute_semantic_reward(
            quality_score=outcome.get("quality_score", 0.5),
            grounding_score=outcome.get("grounding_score", 0.5),
            cost_efficiency=outcome.get("cost_efficiency", 0.5),
            user_intent_match=outcome.get("user_intent_match", 0.5),
            task_id=task_id,
        )
        return reward

    def update(self, transition: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Update bandit with reward signal."""
        arm_id = transition.get("action")
        reward = transition.get("reward", 0.0)
        if arm_id:
            self.update_reward(arm_id, reward)
        return {"updated": bool(arm_id), "reward": reward}

    def export_policy(self) -> Dict[str, Any]:
        """Export current bandit policy snapshot."""
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "algorithm": self.algorithm,
            "arms": {k: v.model_dump() for k, v in self.state.arms.items()},
            "total_pulls": self.state.total_pulls,
        }


# Singleton instances for different policy types
_selectors: Dict[str, BanditSelector] = {}

def get_bandit_selector(policy_type: str, algorithm: str = "ucb1") -> BanditSelector:
    """Get bandit selector for a specific policy type"""
    global _selectors
    
    if policy_type not in _selectors:
        state_path = f"artifacts/learning/bandit_{policy_type}.json"
        _selectors[policy_type] = BanditSelector(state_path=state_path, algorithm=algorithm)
    
    return _selectors[policy_type]



