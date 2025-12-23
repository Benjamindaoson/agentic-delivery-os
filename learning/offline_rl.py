"""
Offline RL - Safe reinforcement learning from replay buffer
Upgraded to implement AbstractPolicy and use semantic reward.
"""

from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import json
import os
from datetime import datetime
from collections import deque

from learning.abstract_policy import AbstractPolicy
from learning.semantic_task_success import compute_semantic_reward


class OfflineRLAgent(AbstractPolicy):
    """
    Offline Reinforcement Learning
    Learns from historical data without online interaction
    Uses Conservative Q-Learning (CQL) principles
    """
    
    def __init__(
        self,
        state_dim: int = 15,
        action_space: List[str] = None,
        learning_rate: float = 0.001,
        discount_factor: float = 0.99,
        buffer_size: int = 10000,
        artifacts_path: str = "artifacts/learning/offline_rl"
    ):
        self.state_dim = state_dim
        self.action_space = action_space or ["sequential", "parallel", "hierarchical"]
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.buffer_size = buffer_size
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Replay buffer: (state, action, reward, next_state, done)
        self.replay_buffer: deque = deque(maxlen=buffer_size)
        
        # Q-function approximation (simple: action -> Q-value estimate)
        self.q_values: Dict[str, float] = {action: 0.0 for action in self.action_space}
        self.q_counts: Dict[str, int] = {action: 0 for action in self.action_space}
        
        # Conservative penalty
        self.conservative_penalty = 0.1
        
        # Statistics
        self.stats = {
            "total_updates": 0,
            "buffer_size": 0,
            "avg_reward": 0.0,
            "policy_entropy": 0.0
        }
        
        # Shadow mode flag
        self.shadow_mode = True
        self.approved_for_production = False
    
    def extract_state(self, run_info: Dict[str, Any]) -> np.ndarray:
        """Extract state vector from run information"""
        state = np.zeros(self.state_dim)
        
        # Goal type (first 5 dims)
        goal_types = ["retrieve", "analyze", "build", "qa", "summarize"]
        goal_type = run_info.get("goal_type", "unknown")
        if goal_type in goal_types:
            state[goal_types.index(goal_type)] = 1.0
        
        # Complexity (dim 5)
        complexity_map = {"simple": 0.25, "moderate": 0.5, "complex": 0.75, "expert": 1.0}
        state[5] = complexity_map.get(run_info.get("complexity", "moderate"), 0.5)
        
        # Cost constraint (dim 6)
        state[6] = min(1.0, run_info.get("max_cost", 1.0) / 2.0)
        
        # Risk level (dim 7)
        risk_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        state[7] = risk_map.get(run_info.get("risk_level", "medium"), 0.5)
        
        # Historical metrics (dims 8-14)
        state[8] = run_info.get("historical_success_rate", 0.5)
        state[9] = run_info.get("historical_avg_cost", 0.5)
        state[10] = run_info.get("historical_avg_latency", 0.5)
        state[11] = run_info.get("failure_rate", 0.1)
        state[12] = run_info.get("retry_count", 0.0) / 5.0  # Normalize
        state[13] = run_info.get("evidence_quality", 0.8)
        state[14] = datetime.now().hour / 24.0  # Time of day
        
        return state
    
    def compute_reward(self, run_result: Dict[str, Any]) -> float:
        """Compute unified semantic reward."""
        reward, _ = compute_semantic_reward(
            quality_score=run_result.get("quality_score", 0.5),
            grounding_score=run_result.get("grounding_score", 0.5),
            cost_efficiency=run_result.get("cost_efficiency", 0.5),
            user_intent_match=run_result.get("user_intent_match", 0.5),
            task_id=run_result.get("task_id"),
        )
        return reward
    
    def add_experience(
        self,
        state: np.ndarray,
        action: str,
        reward: float,
        next_state: np.ndarray,
        done: bool = False
    ):
        """Add experience to replay buffer"""
        self.replay_buffer.append((state, action, reward, next_state, done))
        self.stats["buffer_size"] = len(self.replay_buffer)
    
    def train(self, batch_size: int = 32, num_epochs: int = 10) -> Dict[str, float]:
        """
        Train Q-function from replay buffer
        Uses conservative updates to avoid overestimation
        """
        if len(self.replay_buffer) < batch_size:
            return {"error": "Insufficient data"}
        
        losses = []
        
        for epoch in range(num_epochs):
            # Sample batch
            indices = np.random.choice(len(self.replay_buffer), batch_size, replace=False)
            batch = [self.replay_buffer[i] for i in indices]
            
            # Update Q-values
            for state, action, reward, next_state, done in batch:
                # Conservative Q-Learning update
                current_q = self.q_values[action]
                
                # Compute target (simplified: use reward + discounted next best Q)
                if not done:
                    next_max_q = max(self.q_values.values())
                    target_q = reward + self.discount_factor * next_max_q
                else:
                    target_q = reward
                
                # Conservative penalty (underestimate Q-values for safety)
                target_q -= self.conservative_penalty
                
                # Update Q-value (exponential moving average)
                self.q_values[action] = (
                    (1 - self.learning_rate) * current_q +
                    self.learning_rate * target_q
                )
                self.q_counts[action] += 1
                
                # Track loss
                losses.append(abs(target_q - current_q))
            
            self.stats["total_updates"] += 1
        
        # Update statistics
        all_rewards = [exp[2] for exp in self.replay_buffer]
        self.stats["avg_reward"] = sum(all_rewards) / len(all_rewards) if all_rewards else 0
        
        # Compute policy entropy (diversity measure)
        q_array = np.array(list(self.q_values.values()))
        probs = np.exp(q_array) / np.sum(np.exp(q_array))
        self.stats["policy_entropy"] = -np.sum(probs * np.log(probs + 1e-10))
        
        return {
            "avg_loss": sum(losses) / len(losses) if losses else 0,
            "updates": num_epochs * batch_size,
            "buffer_size": len(self.replay_buffer)
        }
    
    def select_action_policy(self, state: np.ndarray, epsilon: float = 0.0) -> str:
        """
        Select action using learned Q-function
        epsilon: exploration rate (0 = greedy, >0 = epsilon-greedy)
        """
        if np.random.random() < epsilon:
            # Explore: random action
            return np.random.choice(self.action_space)
        
        # Exploit: best action according to Q-function
        return max(self.q_values, key=self.q_values.get)
    
    def evaluate_policy(self, test_episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate current policy on test episodes"""
        total_reward = 0.0
        action_distribution = {action: 0 for action in self.action_space}
        
        for episode in test_episodes:
            state = self.extract_state(episode)
            action = self.select_action_policy(state)
            action_distribution[action] += 1
            
            # Simulate reward (in production, would run actual execution)
            reward = episode.get("actual_reward", 0.5)
            total_reward += reward
        
        return {
            "avg_reward": total_reward / len(test_episodes) if test_episodes else 0,
            "action_distribution": action_distribution,
            "evaluated_at": datetime.now().isoformat()
        }
    
    def approve_for_production(self, validation_result: Dict[str, Any]) -> bool:
        """
        Approve policy for production use
        Requires passing validation thresholds
        """
        if not self.shadow_mode:
            return False
        
        # Check validation metrics
        avg_reward = validation_result.get("avg_reward", 0)
        if avg_reward < 0.5:  # Threshold
            return False
        
        self.approved_for_production = True
        self.shadow_mode = False
        return True
    
    def save_policy(self):
        """Persist learned policy"""
        policy = {
            "q_values": self.q_values,
            "q_counts": self.q_counts,
            "stats": self.stats,
            "shadow_mode": self.shadow_mode,
            "approved_for_production": self.approved_for_production,
            "saved_at": datetime.now().isoformat()
        }
        
        path = os.path.join(self.artifacts_path, "offline_rl_policy.json")
        with open(path, 'w') as f:
            json.dump(policy, f, indent=2)

    # ==== AbstractPolicy interface ====
    def encode_state(self, context: Dict[str, Any]) -> np.ndarray:
        return self.extract_state(context)

    def select_action(self, state: np.ndarray, **kwargs) -> str:
        epsilon = kwargs.get("epsilon", 0.0)
        return self.select_action_policy(state, epsilon)

    def update(self, transition: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Update with a single transition and train lightly.
        transition: {state, action, reward, next_state, done}
        """
        state = transition.get("state")
        action = transition.get("action")
        reward = transition.get("reward", 0.0)
        next_state = transition.get("next_state", np.zeros(self.state_dim))
        done = transition.get("done", False)

        if state is not None and action is not None:
            self.add_experience(state, action, reward, next_state, done)
            train_stats = self.train(batch_size=min(32, len(self.replay_buffer)), num_epochs=1)
        else:
            train_stats = {"updated": False}

        return {"updated": True, "train_stats": train_stats}

    def export_policy(self) -> Dict[str, Any]:
        return {
            "policy_id": "offline_rl",
            "version": "1.0",
            "q_values": self.q_values,
            "stats": self.stats,
            "shadow_mode": self.shadow_mode,
            "approved_for_production": self.approved_for_production,
        }


# Global offline RL agent
_rl_agent: Optional[OfflineRLAgent] = None

def get_offline_rl_agent() -> OfflineRLAgent:
    """Get global offline RL agent"""
    global _rl_agent
    if _rl_agent is None:
        _rl_agent = OfflineRLAgent()
    return _rl_agent



