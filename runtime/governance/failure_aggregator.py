"""
Failure Aggregator: aggregates failures across runs.
"""
import os
import json
from collections import Counter
from typing import Dict, Any, List


class FailureAggregator:
    def __init__(self, base_dir: str = "artifacts/failures"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def record(self, run_id: str, failure: Dict[str, Any]):
        path = os.path.join(self.base_dir, f"{run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(failure, f, indent=2, ensure_ascii=False)

    def aggregate(self) -> Dict[str, Any]:
        failures: List[Dict[str, Any]] = []
        for fname in os.listdir(self.base_dir):
            if fname.endswith(".json"):
                with open(os.path.join(self.base_dir, fname), "r", encoding="utf-8") as f:
                    failures.append(json.load(f))
        node_counter = Counter()
        type_counter = Counter()
        path_counter = Counter()
        agent_counter = Counter()
        profiles: List[Dict[str, Any]] = []
        for f in failures:
            node_counter.update(f.get("failed_nodes", []))
            type_counter.update([f.get("failure_type", "unknown")])
            path_counter.update([f.get("execution_path", "unknown")])
            agent_counter.update([f.get("failed_agent", "unknown")])
            profiles.append(f.get("input_profile", {}))
        result = {
            "failure_pattern": {
                "by_node": node_counter,
                "by_type": type_counter,
                "by_path": path_counter,
                "by_agent": agent_counter,
                "input_profiles": profiles,
            }
        }
        out_path = os.path.join(self.base_dir, "failure_pattern.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return result


failure_aggregator_singleton = FailureAggregator()

