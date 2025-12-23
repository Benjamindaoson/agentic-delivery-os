"""
Strategy Selector (Bandit / RL Hook)

Selects retrieval policies, prompt templates, and tool strategies using
epsilon-greedy with contextual support. Logs decisions for replay/diff.
"""
import os
import json
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ArmStats:
    arm_id: str
    pulls: int = 0
    successes: int = 0
    total_reward: float = 0.0

    def update(self, reward: float) -> None:
        self.pulls += 1
        self.total_reward += reward
        if reward > 0:
            self.successes += 1

    @property
    def average_reward(self) -> float:
        return self.total_reward / self.pulls if self.pulls else 0.0


@dataclass
class StrategyDecision:
    strategy_type: str
    context: Dict[str, Any]
    chosen_arm: str
    epsilon: float
    reason: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StrategySelector:
    """
    Epsilon-greedy strategy selector with contextual fallback.

    Supports:
    - retrieval policies
    - prompt templates
    - tool strategies
    """

    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        epsilon: float = 0.1,
        seed: int = 42,
    ):
        self.artifacts_dir = artifacts_dir
        self.output_path = os.path.join(artifacts_dir, "strategy_decisions.json")
        os.makedirs(self.artifacts_dir, exist_ok=True)
        random.seed(seed)
        self.epsilon = epsilon
        self._decisions: List[StrategyDecision] = []
        self._arms: Dict[str, Dict[str, ArmStats]] = {
            "retrieval": {},
            "prompt": {},
            "tool": {},
        }
        self._load()

    async def choose(
        self,
        strategy_type: str,
        candidate_ids: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> StrategyDecision:
        """
        Choose an arm using epsilon-greedy.
        """
        if strategy_type not in self._arms:
            raise ValueError(f"Unsupported strategy_type: {strategy_type}")
        context = context or {}

        # Ensure stats exist
        for cid in candidate_ids:
            if cid not in self._arms[strategy_type]:
                self._arms[strategy_type][cid] = ArmStats(arm_id=cid)

        explore = random.random() < self.epsilon
        if explore:
            chosen = random.choice(candidate_ids)
            reason = "explore"
        else:
            chosen = max(
                candidate_ids,
                key=lambda cid: self._arms[strategy_type][cid].average_reward,
            )
            reason = "exploit"

        decision = StrategyDecision(
            strategy_type=strategy_type,
            context=context,
            chosen_arm=chosen,
            epsilon=self.epsilon,
            reason=reason,
            timestamp=datetime.now().isoformat(),
        )
        self._decisions.append(decision)
        self._save()
        return decision

    async def update_reward(
        self,
        strategy_type: str,
        arm_id: str,
        reward: float,
    ) -> None:
        """Update reward for an arm."""
        if strategy_type not in self._arms or arm_id not in self._arms[strategy_type]:
            return
        self._arms[strategy_type][arm_id].update(reward)
        self._save()

    def get_stats(self) -> Dict[str, Any]:
        return {
            strategy: {arm_id: asdict(stats) for arm_id, stats in arms.items()}
            for strategy, arms in self._arms.items()
        }

    def _load(self) -> None:
        if not os.path.exists(self.output_path):
            return
        try:
            with open(self.output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("decisions", []):
                self._decisions.append(
                    StrategyDecision(
                        strategy_type=d.get("strategy_type", ""),
                        context=d.get("context", {}),
                        chosen_arm=d.get("chosen_arm", ""),
                        epsilon=d.get("epsilon", self.epsilon),
                        reason=d.get("reason", ""),
                        timestamp=d.get("timestamp", ""),
                    )
                )
            for strategy, arms in data.get("arms", {}).items():
                if strategy not in self._arms:
                    self._arms[strategy] = {}
                for arm_id, stats in arms.items():
                    self._arms[strategy][arm_id] = ArmStats(
                        arm_id=arm_id,
                        pulls=stats.get("pulls", 0),
                        successes=stats.get("successes", 0),
                        total_reward=stats.get("total_reward", 0.0),
                    )
        except (json.JSONDecodeError, IOError):
            return

    def _save(self) -> None:
        data = {
            "decisions": [d.to_dict() for d in self._decisions[-5000:]],
            "arms": {
                strategy: {arm_id: asdict(stats) for arm_id, stats in arms.items()}
                for strategy, arms in self._arms.items()
            },
            "generated_at": datetime.now().isoformat(),
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)



