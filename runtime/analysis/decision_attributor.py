"""
Decision Attribution Engine

Convert parallel signals into a weighted primary root cause for failed runs.

Constraints:
- Async API
- Shadow-only (reads signals, writes attribution artifact)
- Removable without affecting execution
- Outputs JSON artifacts for replay/diff
"""
import os
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List
from datetime import datetime


PRIMARY_CAUSES = [
    "TOOL_TIMEOUT",
    "RETRIEVAL_MISS",
    "PROMPT_MISMATCH",
    "PLANNER_ERROR",
    "UNKNOWN",
]


@dataclass
class AttributionResult:
    """Attribution result schema."""

    run_id: str
    failure: bool
    primary_cause: str
    confidence: float
    supporting_signals: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not self.created_at:
            data["created_at"] = datetime.now().isoformat()
        return data


class DecisionAttributor:
    """
    Decision Attribution Engine.

    Consumes multi-layer signals and assigns one primary root cause.
    """

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_dir = os.path.join(artifacts_dir, "attributions")
        os.makedirs(self.output_dir, exist_ok=True)

    async def attribute(
        self,
        run_id: str,
        run_signals: Dict[str, Any],
        planner_decision: Optional[Dict[str, Any]] = None,
        tool_stats: Optional[Dict[str, Any]] = None,
        retrieval_stats: Optional[Dict[str, Any]] = None,
        prompt_stats: Optional[Dict[str, Any]] = None,
    ) -> AttributionResult:
        """
        Attribute primary cause for a run.

        Args:
            run_id: run identifier
            run_signals: per-run signals (Tool → Retrieval → Evidence → Generation)
            planner_decision: optional planner path/metadata
            tool_stats: optional global tool stats
            retrieval_stats: optional global retrieval stats
            prompt_stats: optional global prompt stats

        Returns:
            AttributionResult
        """
        failure = not run_signals.get("run_success", True)

        # If run succeeded, still emit neutral attribution for completeness.
        if not failure:
            result = AttributionResult(
                run_id=run_id,
                failure=False,
                primary_cause="UNKNOWN",
                confidence=0.0,
                supporting_signals={"note": "run_success"},
                created_at=datetime.now().isoformat(),
            )
            self._persist(result)
            return result

        # Weighted scoring
        scores: Dict[str, float] = {cause: 0.0 for cause in PRIMARY_CAUSES}
        signals = run_signals or {}

        # ---- Tool signals ----
        failure_types = (signals.get("tool_failure_types") or {})
        timeout_score = failure_types.get("TIMEOUT", 0) * 1.0
        permission_score = failure_types.get("PERMISSION_DENIED", 0) * 0.6
        invalid_score = failure_types.get("INVALID_INPUT", 0) * 0.5
        env_score = failure_types.get("ENVIRONMENT_ERROR", 0) * 0.4
        scores["TOOL_TIMEOUT"] += timeout_score + permission_score + invalid_score + env_score

        # If tool success rate low
        tool_success_rate = signals.get("tool_success_rate", 1.0)
        if tool_success_rate < 0.7:
            scores["TOOL_TIMEOUT"] += (0.7 - tool_success_rate) * 2.0

        # ---- Retrieval signals ----
        evidence_usage_rate = signals.get("evidence_usage_rate", 0.0)
        retrieval_num_docs = signals.get("retrieval_num_docs", 0)
        retrieval_policy_sr = signals.get("retrieval_policy_historical_success_rate", 1.0)

        if evidence_usage_rate < 0.3:
            scores["RETRIEVAL_MISS"] += (0.3 - evidence_usage_rate) * 3.0
        if retrieval_num_docs == 0:
            scores["RETRIEVAL_MISS"] += 1.5
        if retrieval_policy_sr < 0.6:
            scores["RETRIEVAL_MISS"] += (0.6 - retrieval_policy_sr) * 2.0

        # ---- Prompt signals ----
        gen_cost = signals.get("generation_cost", 0.0)
        gen_latency = signals.get("generation_latency_ms", 0.0)
        prompt_template_id = signals.get("generation_template_id", "")
        prompt_stats_data = (prompt_stats or {}).get("templates", {})
        prompt_key = prompt_template_id if prompt_template_id in prompt_stats_data else None
        prompt_success_rate = 1.0
        if prompt_key:
            prompt_success_rate = prompt_stats_data[prompt_key].get("success_rate", 1.0)
        if prompt_success_rate < 0.7:
            scores["PROMPT_MISMATCH"] += (0.7 - prompt_success_rate) * 2.5
        if gen_latency > 2000:  # high latency often indicates prompt/tool mismatch
            scores["PROMPT_MISMATCH"] += min(gen_latency / 4000, 1.0)
        if gen_cost > 0.5:
            scores["PROMPT_MISMATCH"] += 0.5

        # ---- Planner signals ----
        planner_path = (planner_decision or {}).get("path", [])
        planner_mode = (planner_decision or {}).get("mode", "")
        if planner_mode in ["degraded", "minimal", "fallback"]:
            scores["PLANNER_ERROR"] += 1.0
        if planner_path and isinstance(planner_path, list) and "retry" in planner_path:
            scores["PLANNER_ERROR"] += 0.5
        historical_sr = signals.get("pattern_historical_success_rate", 0.0)
        if historical_sr < 0.3:
            scores["PLANNER_ERROR"] += (0.3 - historical_sr) * 1.5

        # Normalize to pick primary cause
        primary_cause, confidence = self._pick_primary(scores)
        supporting = {
            "scores": scores,
            "tool_failure_types": failure_types,
            "evidence_usage_rate": evidence_usage_rate,
            "retrieval_policy_sr": retrieval_policy_sr,
            "prompt_success_rate": prompt_success_rate,
            "planner_mode": planner_mode,
            "planner_path": planner_path,
        }

        result = AttributionResult(
            run_id=run_id,
            failure=True,
            primary_cause=primary_cause,
            confidence=confidence,
            supporting_signals=supporting,
            created_at=datetime.now().isoformat(),
        )
        self._persist(result)
        return result

    def _pick_primary(self, scores: Dict[str, float]) -> (str, float):
        """Pick the highest-scoring cause with normalized confidence."""
        total = sum(scores.values())
        if total <= 0:
            return "UNKNOWN", 0.0
        primary = max(scores.items(), key=lambda kv: kv[1])
        return primary[0], min(primary[1] / total, 1.0)

    def _persist(self, result: AttributionResult) -> None:
        """Persist attribution to artifacts for replay/diff."""
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, f"{result.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        # maintain latest pointer for Learning consumption
        latest_path = os.path.join(self.output_dir, "latest.json")
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        # compatibility: write to artifacts/attribution/{run_id}.json as well
        alt_dir = os.path.join(os.path.dirname(self.output_dir), "attribution")
        os.makedirs(alt_dir, exist_ok=True)
        alt_path = os.path.join(alt_dir, f"{result.run_id}.json")
        with open(alt_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load an existing attribution artifact."""
        path = os.path.join(self.output_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

