"""
Contextual Bandit - Context-aware strategy selection
L6 Component: Advanced Learning - Contextual Bandit
"""

from typing import Dict, List, Any, Optional
import numpy as np
import json
import os
from datetime import datetime


class ContextualBandit:
    """
    Contextual multi-armed bandit
    Selects strategies based on context (goal type, task features, cost constraints)
    Uses LinUCB algorithm
    """
    
    def __init__(
        self,
        arms: List[str],
        context_dim: int = 10,
        alpha: float = 0.5,
        artifacts_path: str = "artifacts/learning/contextual_bandit"
    ):
        self.arms = arms
        self.context_dim = context_dim
        self.alpha = alpha  # Exploration parameter
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # LinUCB parameters for each arm
        self.A = {arm: np.identity(context_dim) for arm in arms}  # A = D^T D + I
        self.b = {arm: np.zeros(context_dim) for arm in arms}     # b = D^T c
        
        # Statistics
        self.stats = {
            "total_pulls": 0,
            "pulls_per_arm": {arm: 0 for arm in arms},
            "rewards_per_arm": {arm: 0.0 for arm in arms}
        }
    
    def extract_context(self, run_info: Dict[str, Any]) -> np.ndarray:
        """
        Extract feature vector from run context
        Features: goal_type (one-hot), complexity, cost_constraint, etc.
        """
        context = np.zeros(self.context_dim)
        
        # Goal type (first 5 dims)
        goal_types = ["retrieve", "analyze", "build", "qa", "summarize"]
        goal_type = run_info.get("goal_type", "unknown")
        if goal_type in goal_types:
            context[goal_types.index(goal_type)] = 1.0
        
        # Complexity (dim 5)
        complexity_map = {"simple": 0.25, "moderate": 0.5, "complex": 0.75, "expert": 1.0}
        context[5] = complexity_map.get(run_info.get("complexity", "moderate"), 0.5)
        
        # Cost constraint (dim 6)
        max_cost = run_info.get("max_cost", 1.0)
        context[6] = min(1.0, max_cost / 2.0)  # Normalize
        
        # Risk level (dim 7)
        risk_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        context[7] = risk_map.get(run_info.get("risk_level", "medium"), 0.5)
        
        # Historical success rate for this goal type (dim 8)
        context[8] = run_info.get("historical_success_rate", 0.5)
        
        # Time of day (dim 9) - might affect load
        hour = datetime.now().hour
        context[9] = hour / 24.0
        
        return context
    
    def select_arm(self, context: np.ndarray) -> str:
        """
        Select arm using LinUCB algorithm
        Returns: selected arm (strategy)
        """
        ucb_scores = {}
        
        for arm in self.arms:
            # Compute theta (parameter estimate)
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            
            # Compute UCB
            p = theta.T @ context
            sigma = np.sqrt(context.T @ A_inv @ context)
            ucb = p + self.alpha * sigma
            
            ucb_scores[arm] = ucb
        
        # Select arm with highest UCB
        selected_arm = max(ucb_scores, key=ucb_scores.get)
        
        self.stats["total_pulls"] += 1
        self.stats["pulls_per_arm"][selected_arm] += 1
        
        return selected_arm
    
    def update(self, arm: str, context: np.ndarray, reward: float):
        """
        Update bandit with observed reward
        """
        # Update A and b for this arm
        self.A[arm] += np.outer(context, context)
        self.b[arm] += reward * context
        
        # Update stats
        self.stats["rewards_per_arm"][arm] += reward
    
    def get_arm_performance(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for each arm"""
        performance = {}
        
        for arm in self.arms:
            pulls = self.stats["pulls_per_arm"][arm]
            total_reward = self.stats["rewards_per_arm"][arm]
            
            performance[arm] = {
                "pulls": pulls,
                "avg_reward": total_reward / pulls if pulls > 0 else 0,
                "pull_percentage": pulls / self.stats["total_pulls"] * 100 if self.stats["total_pulls"] > 0 else 0
            }
        
        return performance
    
    def save_state(self):
        """Persist bandit state"""
        state = {
            "arms": self.arms,
            "context_dim": self.context_dim,
            "alpha": self.alpha,
            "stats": self.stats,
            "performance": self.get_arm_performance(),
            "saved_at": datetime.now().isoformat()
        }
        
        # Note: Not saving numpy arrays (A, b) for simplicity
        # In production, use pickle or numpy.save
        
        path = os.path.join(self.artifacts_path, "contextual_bandit_state.json")
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)


# Global contextual bandit
_bandit: Optional[ContextualBandit] = None

def get_contextual_bandit(
    arms: List[str] = None,
    context_dim: int = 10
) -> ContextualBandit:
    """Get global contextual bandit"""
    global _bandit
    if _bandit is None:
        if arms is None:
            arms = ["sequential", "parallel", "hierarchical"]
        _bandit = ContextualBandit(arms=arms, context_dim=context_dim)
    return _bandit



