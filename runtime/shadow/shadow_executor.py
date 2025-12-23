"""
Shadow Execution Engine

Execute active and candidate policies side-by-side with no user-visible effects.

Constraints:
- Async API
- No side effects (shadow only)
- Writes JSON diff artifacts for replay/diff
"""
import os
import json
from typing import Dict, Any, Callable, Awaitable, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ShadowResult:
    """Captures active vs candidate comparison."""

    run_id: str
    decision_divergence: bool
    cost_delta: float
    latency_delta: float
    success_delta: float
    active: Dict[str, Any]
    candidate: Dict[str, Any]
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data["created_at"]:
            data["created_at"] = datetime.now().isoformat()
        return data


class ShadowExecutor:
    """
    Shadow executor to compare active vs candidate policy decisions.

    It requires callers to provide execution callables; the executor itself performs
    no side effects besides writing comparison artifacts.
    """

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_dir = os.path.join(artifacts_dir, "shadow_diff")
        os.makedirs(self.output_dir, exist_ok=True)

    async def run_shadow(
        self,
        run_id: str,
        input_payload: Dict[str, Any],
        active_runner: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        candidate_runner: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> ShadowResult:
        """
        Execute active (real) and candidate (shadow) paths.

        Runner callables must not mutate external state. Shadow execution result is
        persisted to artifacts/shadow_diff/{run_id}.json.
        """
        active_res = await active_runner(dict(input_payload))
        candidate_res = await candidate_runner(dict(input_payload))

        decision_divergence = active_res.get("decision") != candidate_res.get("decision")
        cost_delta = candidate_res.get("cost", 0.0) - active_res.get("cost", 0.0)
        latency_delta = candidate_res.get("latency_ms", 0.0) - active_res.get("latency_ms", 0.0)
        success_delta = (
            (1 if candidate_res.get("success") else 0) - (1 if active_res.get("success") else 0)
        )

        result = ShadowResult(
            run_id=run_id,
            decision_divergence=decision_divergence,
            cost_delta=cost_delta,
            latency_delta=latency_delta,
            success_delta=success_delta,
            active=active_res,
            candidate=candidate_res,
            created_at=datetime.now().isoformat(),
        )
        self._save(result)
        return result

    def _save(self, result: ShadowResult) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, f"{result.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        # compatibility: also under artifacts/eval/shadow_diff
        alt_dir = os.path.join(self.artifacts_dir, "eval", "shadow_diff")
        os.makedirs(alt_dir, exist_ok=True)
        alt_path = os.path.join(alt_dir, f"{result.run_id}.json")
        with open(alt_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.output_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

