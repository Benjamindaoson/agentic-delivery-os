"""
Failure Budget + Risk Guard

Rolling window budget across failures, cost, latency.
Artifacts: artifacts/exploration/budget_state.json
"""
import os
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any

DEFAULT_WINDOW_RUNS = 200


@dataclass
class BudgetState:
    schema_version: str
    window: Dict[str, Any]
    remaining: Dict[str, float]
    spent: Dict[str, float]
    guards: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FailureBudget:
    """Rolling budget for controlled exploration."""

    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        window_runs: int = DEFAULT_WINDOW_RUNS,
        max_failures: int = 10,
        max_cost_usd: float = 5.0,
        max_latency_ms: float = 20000.0,
    ):
        self.artifacts_dir = artifacts_dir
        self.state_path = os.path.join(artifacts_dir, "exploration", "budget_state.json")
        self.window_runs = window_runs
        self.max_failures = max_failures
        self.max_cost_usd = max_cost_usd
        self.max_latency_ms = max_latency_ms
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self.state = self._load_or_init()

    def can_spend(self, failures: int, cost_usd: float, latency_ms: float) -> bool:
        """Check if budget allows spending."""
        if self.state["guards"]["hard_stop"]:
            return False
        return (
            self.state["remaining"]["failures"] - failures >= 0
            and self.state["remaining"]["cost_usd"] - cost_usd >= 0
            and self.state["remaining"]["latency_ms"] - latency_ms >= 0
        )

    def spend(self, failures: int, cost_usd: float, latency_ms: float) -> Dict[str, Any]:
        """Spend budget and persist."""
        allowed = self.can_spend(failures, cost_usd, latency_ms)
        if not allowed:
            self.state["guards"]["hard_stop"] = True
            self.state["guards"]["last_stop_reason"] = "budget_exhausted"
        else:
            self.state["remaining"]["failures"] -= failures
            self.state["remaining"]["cost_usd"] -= cost_usd
            self.state["remaining"]["latency_ms"] -= latency_ms
            self.state["spent"]["failures"] += failures
            self.state["spent"]["cost_usd"] += cost_usd
            self.state["spent"]["latency_ms"] += latency_ms
        self._persist()
        return self.state

    def reset(self) -> None:
        self.state = self._init_state()
        self._persist()

    def _load_or_init(self) -> Dict[str, Any]:
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        state = self._init_state()
        self._persist(state)
        return state

    def _init_state(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "window": {"type": "rolling", "size_runs": self.window_runs},
            "remaining": {
                "failures": self.max_failures,
                "cost_usd": self.max_cost_usd,
                "latency_ms": self.max_latency_ms,
            },
            "spent": {"failures": 0, "cost_usd": 0.0, "latency_ms": 0.0},
            "guards": {"hard_stop": False, "last_stop_reason": None},
            "timestamp": datetime.now().isoformat(),
        }

    def _persist(self, state: Dict[str, Any] = None) -> None:
        state = state or self.state
        state["timestamp"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)



