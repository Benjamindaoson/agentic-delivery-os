"""
Executor for Data Intelligence Agent.
Runs classification, strategy enumeration, policy resolution, and evidence emission.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

from runtime.data_intel import type_classifier
from runtime.data_intel import strategy_enumerator
from runtime.data_intel import tradeoff_analyzer
from runtime.data_intel import policy_resolver
from runtime.data_intel import cost_engine
from runtime.data_intel import capability_snapshot


@dataclass
class EvidencePack:
    input_snapshot_hash: str
    policy_hash: str
    strategy_plan_hash: str
    decision_hash: str
    run_id: str
    selected_policy_id: str
    rejected_policies: List[str]
    decision_path: List[Dict[str, Any]]
    cost_estimate: Any
    latency_class: Any
    risk_profile: Any
    user_constraint_snapshot: Any
    roi_manifest: Any
    admission_decision: Any
    chosen_strategy: Dict[str, Any]
    resolution: Dict[str, Any]
    classifications: List[Dict[str, Any]]
    strategies: List[Dict[str, Any]]
    tradeoffs: List[Dict[str, Any]]
    timestamp: str


class DataIntelExecutor:
    def __init__(self, base_dir: str = "artifacts/data_intel"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _hash_json(self, obj: Any) -> str:
        return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()

    def _generate_run_id(self, inputs: List[Dict], policy: Dict) -> str:
        seed = f"{self._hash_json(inputs)}_{self._hash_json(policy)}_{datetime.now().isoformat()}"
        return f"run_{self._hash_json(seed)[:16]}"

    def _store_json(self, path: str, data: Any):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def run(
        self,
        input_files: List[Dict[str, Any]],
        tenant_context: Dict[str, Any],
        tenant_policy: Dict[str, Any] = None,
        system_constraints: Dict[str, Any] = None,
        runtime_capabilities: Dict[str, Any] = None,
        runtime_tools: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the deterministic pipeline and persist evidence.
        """
        system_constraints = system_constraints or {}
        runtime_capabilities = runtime_capabilities or {}
        runtime_tools = runtime_tools or []

        classifications = type_classifier.classify_inputs(input_files)
        strategies = strategy_enumerator.enumerate_for_files(classifications)
        tradeoffs = tradeoff_analyzer.analyze(strategies)
        capability_snap = capability_snapshot.capture_runtime_capabilities(runtime_tools)

        resolutions = []
        chosen_strategies = []
        rejected = []
        decision_path = []
        for strat_entry, trade_entry in zip(strategies, tradeoffs):
            res = policy_resolver.resolve(
                file_entry=strat_entry,
                tradeoff_entry=trade_entry,
                tenant_policy=tenant_policy,
                tenant_context=tenant_context,
                system_constraints=system_constraints,
            )
            resolutions.append(res)
            # pick chosen strategy
            chosen = next(
                (s for s in strat_entry.get("strategies", []) if s.get("id") == res.get("chosen_strategy_id")),
                strat_entry.get("strategies", [{}])[0] if strat_entry.get("strategies") else {},
            )
            # rejected strategies
            rejected_ids = [s.get("id") for s in strat_entry.get("strategies", []) if s.get("id") != chosen.get("id")]
            rejected.extend(rejected_ids)
            decision_path.append(
                {
                    "file_path": strat_entry.get("file_path"),
                    "selected": chosen.get("id"),
                    "rejected": rejected_ids,
                    "resolution_status": res.get("status"),
                }
            )
            chosen_strategies.append({"file_path": strat_entry.get("file_path"), "strategy": chosen})

        run_id = self._generate_run_id(input_files, tenant_policy or {})
        run_dir = os.path.join(self.base_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # hashes
        input_snapshot_hash = self._hash_json(input_files)
        policy_hash = self._hash_json(tenant_policy or {})
        strategy_plan_hash = self._hash_json(strategies)
        decision_hash = self._hash_json(resolutions)
        capability_hash = self._hash_json(capability_snap)

        # ROI manifest placeholder (structure value scoring deterministic)
        roi_manifest = []
        for cls in classifications:
            val = cls.get("cheap_signals", {}).get("table_boundary_heuristic", 0.0) + cls.get("cheap_signals", {}).get("image_density", 0.0)
            roi_manifest.append(
                {
                    "unit": "page",
                    "id": cls.get("file_path", ""),
                    "structural_value_score": round(val, 2),
                    "evidence": ["table_density", "numeric_pattern"],
                }
            )

        # Cost model forecast
        forecast = cost_engine.forecast_cost(classifications[0] if classifications else {}, strategies[0].get("strategies", []) if strategies else [])
        actual_cost = forecast["total_cost_estimate"]  # placeholder actual = forecast
        reconciliation = cost_engine.reconcile(forecast["total_cost_estimate"], actual_cost, classifications[0] if classifications else {})

        # derive aggregates
        selected_policy_id = chosen_strategies[0]["strategy"].get("id", "") if chosen_strategies else ""
        latency_class = chosen_strategies[0]["strategy"].get("expected_latency_class") if chosen_strategies else None
        cost_estimate = chosen_strategies[0]["strategy"].get("expected_cost_range") if chosen_strategies else None
        risk_profile = chosen_strategies[0]["strategy"].get("risk_types") if chosen_strategies else None

        evidence = EvidencePack(
            input_snapshot_hash=input_snapshot_hash,
            policy_hash=policy_hash,
            strategy_plan_hash=strategy_plan_hash,
            decision_hash=decision_hash,
            roi_manifest=roi_manifest,
            admission_decision={"status": "accepted"},
            run_id=run_id,
            selected_policy_id=selected_policy_id,
            rejected_policies=rejected,
            decision_path=decision_path,
            cost_estimate=cost_estimate,
            latency_class=latency_class,
            risk_profile=risk_profile,
            user_constraint_snapshot=None,
            chosen_strategy={"by_file": chosen_strategies},
            resolution={"by_file": resolutions},
            classifications=classifications,
            strategies=strategies,
            tradeoffs=tradeoffs,
            timestamp=datetime.now().isoformat(),
        )

        # Persist artifacts
        self._store_json(os.path.join(run_dir, "input_snapshot.json"), input_files)
        self._store_json(os.path.join(run_dir, "tenant_policy.json"), tenant_policy or {})
        self._store_json(os.path.join(run_dir, "strategy_plan.json"), strategies)
        self._store_json(os.path.join(run_dir, "tradeoffs.json"), tradeoffs)
        self._store_json(os.path.join(run_dir, "resolutions.json"), resolutions)
        self._store_json(os.path.join(run_dir, "capability_snapshot.json"), capability_snap)
        self._store_json(os.path.join(run_dir, "roi_manifest.json"), roi_manifest)
        self._store_json(os.path.join(run_dir, "cost_model.json"), forecast)
        self._store_json(os.path.join(run_dir, "cost_reconciliation.json"), reconciliation)
        self._store_json(os.path.join(run_dir, "evidence.json"), asdict(evidence))

        return {
            "run_id": run_id,
            "evidence": asdict(evidence),
        }


executor_singleton = DataIntelExecutor()
