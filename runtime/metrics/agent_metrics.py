"""
Per-agent metrics recording.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any
import json
import os


@dataclass
class AgentMetrics:
    success_rate: float
    latency_p95_ms: float
    cost_per_call: float
    failure_type_distribution: Dict[str, float]


class AgentMetricsStore:
    def __init__(self, base_dir: str = "artifacts/metrics"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def record(self, agent_id: str, metrics: AgentMetrics):
        path = os.path.join(self.base_dir, f"{agent_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(metrics), f, indent=2, ensure_ascii=False)


metrics_store_singleton = AgentMetricsStore()


