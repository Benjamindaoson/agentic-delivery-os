"""
Golden Replay Suite management and execution.

Artifacts:
- artifacts/eval/golden_replay_report_{candidate_id}.json
"""
import os
import json
from typing import List, Dict, Any, Callable, Awaitable
from datetime import datetime


class GoldenReplaySuite:
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_dir = os.path.join(artifacts_dir, "eval")
        os.makedirs(self.output_dir, exist_ok=True)

    def build_suite(
        self,
        fixed_golden: List[Dict[str, Any]],
        recent_failures: List[Dict[str, Any]],
        new_patterns: List[Dict[str, Any]],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        suite = []
        suite.extend(fixed_golden)
        suite.extend(recent_failures[: limit // 2])
        suite.extend(new_patterns[: limit // 2])
        return suite[:limit]

    async def run_suite(
        self,
        candidate_id: str,
        suite: List[Dict[str, Any]],
        candidate_runner: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        results = []
        success = 0
        total_cost = 0.0
        total_latency = 0.0
        for item in suite:
            res = await candidate_runner(dict(item))
            results.append(res)
            total_cost += res.get("cost", 0.0)
            total_latency += res.get("latency_ms", 0.0)
            if res.get("success"):
                success += 1
        n = len(suite) or 1
        report = {
            "schema_version": "1.0",
            "candidate_id": candidate_id,
            "success_rate": success / n,
            "avg_cost": total_cost / n,
            "avg_latency_ms": total_latency / n,
            "results": results[:50],  # cap for artifact size
            "timestamp": datetime.now().isoformat(),
        }
        path = os.path.join(self.output_dir, f"golden_replay_report_{candidate_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return report



