"""
Policy-Level KPI Aggregator

Aggregates KPIs by policy (retrieval/prompt/tool combination) using run-level signals
and optional attribution artifacts.

Constraints:
- Async API
- Shadow-only aggregation (read artifacts, write new artifact)
- Removable without impacting execution
- Output JSON: artifacts/policy_kpis.json
"""
import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict, Counter


@dataclass
class PolicyKPI:
    policy_id: str
    success_rate: float = 0.0
    avg_cost: float = 0.0
    avg_latency: float = 0.0
    evidence_utilization_rate: float = 0.0
    failure_cause_distribution: Dict[str, int] = field(default_factory=dict)
    regressions: List[str] = field(default_factory=list)
    total_runs: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyKPIAggregator:
    """Aggregates KPIs per policy across layers."""

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_path = os.path.join(artifacts_dir, "policy_kpis.json")

    async def aggregate(
        self,
        run_signals_path: Optional[str] = None,
        attribution_dir: Optional[str] = None,
        retrieval_stats_path: Optional[str] = None,
        prompt_stats_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate KPIs.

        Args:
            run_signals_path: path to run_signals.json (optional)
            attribution_dir: directory of attribution artifacts (optional)
            retrieval_stats_path: retrieval_policy_stats.json path (optional)
            prompt_stats_path: prompt_stats.json path (optional)
        """
        run_signals_path = run_signals_path or os.path.join(self.artifacts_dir, "run_signals.json")
        attribution_dir = attribution_dir or os.path.join(self.artifacts_dir, "attributions")
        retrieval_stats_path = retrieval_stats_path or os.path.join(
            self.artifacts_dir, "retrieval_policy_stats.json"
        )
        prompt_stats_path = prompt_stats_path or os.path.join(self.artifacts_dir, "prompt_stats.json")

        runs = self._load_run_signals(run_signals_path)
        attributions = self._load_attributions(attribution_dir)
        retrieval_baselines = self._load_json(retrieval_stats_path).get("policies", {})
        prompt_baselines = self._load_json(prompt_stats_path).get("templates", {})

        policy_kpis: Dict[str, PolicyKPI] = {}

        for run in runs:
            retr_id = run.get("retrieval_policy_id") or "unknown_retrieval"
            prompt_id = run.get("generation_template_id") or "unknown_prompt"
            tool_sig = run.get("pattern_hash") or "unknown_tools"

            self._accumulate(policy_kpis, f"retrieval::{retr_id}", run, attributions)
            self._accumulate(policy_kpis, f"prompt::{prompt_id}", run, attributions)
            self._accumulate(policy_kpis, f"tools::{tool_sig}", run, attributions)

        # Add regression hints by comparing to baselines
        for pid, kpi in policy_kpis.items():
            base = None
            if pid.startswith("retrieval::"):
                base = retrieval_baselines.get(pid.split("::", 1)[1])
            elif pid.startswith("prompt::"):
                base = prompt_baselines.get(pid.split("::", 1)[1])
            if base:
                self._compute_regressions(kpi, base)

        output = {
            "policies": {pid: k.to_dict() for pid, k in policy_kpis.items()},
            "generated_at": datetime.now().isoformat(),
        }
        self._save(output)
        return output

    def _accumulate(
        self,
        policy_kpis: Dict[str, PolicyKPI],
        policy_id: str,
        run: Dict[str, Any],
        attributions: Dict[str, Dict[str, Any]],
    ) -> None:
        if policy_id not in policy_kpis:
            policy_kpis[policy_id] = PolicyKPI(policy_id=policy_id)
        kpi = policy_kpis[policy_id]

        kpi.total_runs += 1
        success = run.get("run_success", False)
        kpi.success_rate = (kpi.success_rate * (kpi.total_runs - 1) + (1 if success else 0)) / kpi.total_runs

        cost = run.get("generation_cost", 0.0) + run.get("total_cost", 0.0)
        latency = run.get("generation_latency_ms", 0.0) + run.get("tool_total_latency_ms", 0.0)

        kpi.avg_cost = (kpi.avg_cost * (kpi.total_runs - 1) + cost) / kpi.total_runs
        kpi.avg_latency = (kpi.avg_latency * (kpi.total_runs - 1) + latency) / kpi.total_runs

        kpi.evidence_utilization_rate = (
            (kpi.evidence_utilization_rate * (kpi.total_runs - 1) + run.get("evidence_usage_rate", 0.0))
            / kpi.total_runs
        )

        # failure cause distribution from attribution
        run_id = run.get("run_id")
        cause = None
        if run_id and run_id in attributions:
            cause = attributions[run_id].get("primary_cause")
        if cause:
            kpi.failure_cause_distribution[cause] = kpi.failure_cause_distribution.get(cause, 0) + 1

    def _compute_regressions(self, kpi: PolicyKPI, baseline: Dict[str, Any]) -> None:
        """Compare against baseline stats to detect regressions."""
        regressions: List[str] = []
        base_sr = baseline.get("success_rate", 1.0)
        if base_sr > 0 and kpi.success_rate < base_sr * 0.9:
            regressions.append("success_rate")
        base_latency = baseline.get("avg_latency_ms", baseline.get("avg_latency", 0.0))
        if base_latency and kpi.avg_latency > base_latency * 1.2:
            regressions.append("latency")
        base_cost = baseline.get("avg_cost", 0.0)
        if base_cost and kpi.avg_cost > base_cost * 1.2:
            regressions.append("cost")
        kpi.regressions = regressions

    def _load_run_signals(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("signals", [])
        except (json.JSONDecodeError, IOError):
            return []

    def _load_attributions(self, directory: str) -> Dict[str, Dict[str, Any]]:
        if not os.path.isdir(directory):
            return {}
        results: Dict[str, Dict[str, Any]] = {}
        for filename in os.listdir(directory):
            if not filename.endswith(".json"):
                continue
            run_id = filename.replace(".json", "")
            try:
                with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                    results[run_id] = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
        return results

    def _load_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(self.artifacts_dir, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)



