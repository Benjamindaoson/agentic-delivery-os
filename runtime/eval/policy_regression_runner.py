"""
Automated Regression / Golden Replay Pipeline

Replays historical runs against a candidate policy and compares with golden results.

Constraints:
- Async API
- No changes to execution control flow
- Outputs JSON artifact: artifacts/policy_regression_report.json
"""
import os
import json
from typing import Dict, Any, List, Callable, Awaitable, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class RegressionVerdict:
    candidate_policy_id: str
    pass_regression: bool
    blocking_reasons: List[str]
    safe_to_rollout: bool
    metrics: Dict[str, Any]
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data["created_at"]:
            data["created_at"] = datetime.now().isoformat()
        return data


class PolicyRegressionRunner:
    """
    Replay historical runs against a candidate policy and compare against golden outputs.
    """

    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        threshold_success_drop: float = 0.05,
        threshold_cost_increase: float = 0.1,
        allow_new_failure_modes: bool = False,
    ):
        self.artifacts_dir = artifacts_dir
        self.output_path = os.path.join(artifacts_dir, "policy_regression_report.json")
        self.threshold_success_drop = threshold_success_drop
        self.threshold_cost_increase = threshold_cost_increase
        self.allow_new_failure_modes = allow_new_failure_modes

    async def run(
        self,
        candidate_policy_id: str,
        historical_runs: List[Dict[str, Any]],
        golden_results: List[Dict[str, Any]],
        candidate_runner: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> RegressionVerdict:
        """
        Execute regression evaluation.

        Args:
            candidate_policy_id: candidate policy identifier
            historical_runs: list of input payloads to replay
            golden_results: expected results aligned with historical_runs
            candidate_runner: async callable to execute candidate policy
        """
        blocking_reasons: List[str] = []
        evaluated: List[Dict[str, Any]] = []
        successes = 0
        total_cost = 0.0
        total_latency = 0.0
        failure_modes = set()

        for payload, golden in zip(historical_runs, golden_results):
            res = await candidate_runner(dict(payload))
            evaluated.append(res)
            if res.get("success"):
                successes += 1
            else:
                failure_modes.add(res.get("error_type") or "unknown")
            total_cost += res.get("cost", 0.0)
            total_latency += res.get("latency_ms", 0.0)

            # check golden match
            if golden.get("expected_success") and not res.get("success"):
                blocking_reasons.append("success_regression")

        n = len(historical_runs) if historical_runs else 1
        success_rate = successes / n
        avg_cost = total_cost / n
        avg_latency = total_latency / n

        # Compare to golden aggregate
        golden_success_rate = self._avg([1 if g.get("expected_success") else 0 for g in golden_results])
        golden_cost = self._avg([g.get("expected_cost", 0.0) for g in golden_results])

        if success_rate < golden_success_rate * (1 - self.threshold_success_drop):
            blocking_reasons.append("success_rate_drop")
        if avg_cost > golden_cost * (1 + self.threshold_cost_increase):
            blocking_reasons.append("cost_increase")

        if not self.allow_new_failure_modes:
            golden_failures = {g.get("error_type") for g in golden_results if not g.get("expected_success")}
            new_failures = failure_modes.difference(golden_failures)
            if new_failures:
                blocking_reasons.append("new_failure_modes")

        pass_regression = len(blocking_reasons) == 0
        verdict = RegressionVerdict(
            candidate_policy_id=candidate_policy_id,
            pass_regression=pass_regression,
            blocking_reasons=blocking_reasons,
            safe_to_rollout=pass_regression,
            metrics={
                "success_rate": round(success_rate, 4),
                "avg_cost": round(avg_cost, 4),
                "avg_latency_ms": round(avg_latency, 2),
                "golden_success_rate": golden_success_rate,
                "golden_cost": golden_cost,
            },
            created_at=datetime.now().isoformat(),
        )
        self._save(verdict)
        # also save per-candidate under eval directory
        eval_dir = os.path.join(self.artifacts_dir, "eval")
        os.makedirs(eval_dir, exist_ok=True)
        alt_path = os.path.join(eval_dir, f"golden_replay_report_{candidate_policy_id}.json")
        with open(alt_path, "w", encoding="utf-8") as f:
            json.dump(verdict.to_dict(), f, indent=2, ensure_ascii=False)
        return verdict

    def _avg(self, arr: List[float]) -> float:
        return sum(arr) / len(arr) if arr else 0.0

    def _save(self, verdict: RegressionVerdict) -> None:
        os.makedirs(self.artifacts_dir, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(verdict.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.output_path):
            return None
        with open(self.output_path, "r", encoding="utf-8") as f:
            return json.load(f)

