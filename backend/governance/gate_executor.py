"""
Gate Executor: Industrial-Grade Release Gate Execution
Features:
- Real metric collection from artifacts
- Multi-gate evaluation
- Evidence-based decisions
- Full audit trail
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum


class NoAuthoritativeGateDecision(RuntimeError):
    """Raised when gate_decision.json is missing or malformed."""


class GateDecision(str, Enum):
    """Gate decision outcomes"""
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    BLOCK = "block"
    HOLD = "hold"  # Wait for more data


@dataclass
class GateMetric:
    """A metric for gate evaluation"""
    name: str
    current_value: float
    threshold: float
    operator: str = "gte"  # gte, lte, gt, lt, eq
    weight: float = 1.0
    passed: bool = False
    source: str = ""
    
    def evaluate(self) -> bool:
        """Evaluate if metric passes threshold"""
        ops = {
            "gte": lambda c, t: c >= t,
            "lte": lambda c, t: c <= t,
            "gt": lambda c, t: c > t,
            "lt": lambda c, t: c < t,
            "eq": lambda c, t: abs(c - t) < 0.001
        }
        self.passed = ops.get(self.operator, ops["gte"])(self.current_value, self.threshold)
        return self.passed


@dataclass
class GateEvaluationResult:
    """Result of gate evaluation"""
    gate_name: str
    decision: GateDecision
    metrics: List[GateMetric]
    passed_metrics: int
    total_metrics: int
    weighted_score: float
    reason: str
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "decision": self.decision.value,
            "metrics": [asdict(m) for m in self.metrics]
        }


class MetricCollector:
    """Collects real metrics from artifacts and system state"""
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.artifacts_base = artifacts_base
    
    def collect_metrics(
        self,
        task_id: str,
        metric_definitions: List[Dict[str, Any]]
    ) -> List[GateMetric]:
        """
        Collect metrics based on definitions.
        
        Each definition should have:
        - name: metric name
        - source: where to get it (artifact path or system)
        - threshold: value to compare against
        - operator: comparison operator
        """
        metrics = []
        
        for defn in metric_definitions:
            metric = self._collect_single_metric(task_id, defn)
            metrics.append(metric)
        
        return metrics
    
    def _collect_single_metric(
        self,
        task_id: str,
        definition: Dict[str, Any]
    ) -> GateMetric:
        """Collect a single metric"""
        name = definition.get("name", "unknown")
        source = definition.get("source", "")
        threshold = float(definition.get("threshold", 0))
        operator = definition.get("operator", "gte")
        weight = float(definition.get("weight", 1.0))
        
        # Collect current value based on source
        current_value = self._get_metric_value(task_id, source, name)
        
        metric = GateMetric(
            name=name,
            current_value=current_value,
            threshold=threshold,
            operator=operator,
            weight=weight,
            source=source
        )
        metric.evaluate()
        
        return metric
    
    def _get_metric_value(self, task_id: str, source: str, name: str) -> float:
        """Get metric value from source"""
        
        # Try artifact sources
        if source.startswith("artifact:"):
            artifact_path = source.replace("artifact:", "")
            return self._read_artifact_metric(task_id, artifact_path, name)
        
        # System metrics
        if source == "system:cost":
            return self._get_cost_metric(task_id)
        
        if source == "system:latency":
            return self._get_latency_metric(task_id)
        
        if source == "system:success_rate":
            return self._get_success_rate_metric(task_id)
        
        if source == "system:quality":
            return self._get_quality_metric(task_id)
        
        # Default: try to read from evaluation artifact
        return self._read_evaluation_metric(task_id, name)
    
    def _read_artifact_metric(
        self,
        task_id: str,
        artifact_path: str,
        metric_name: str
    ) -> float:
        """Read metric from artifact file"""
        full_path = os.path.join(self.artifacts_base, "rag_project", task_id, artifact_path)
        
        if not os.path.exists(full_path):
            return 0.0
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Navigate to metric
            if isinstance(data, dict):
                # Try direct key
                if metric_name in data:
                    return float(data[metric_name])
                
                # Try nested paths (e.g., "metrics.quality_score")
                parts = metric_name.split(".")
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return 0.0
                return float(current)
            
            return 0.0
        except Exception:
            return 0.0
    
    def _read_evaluation_metric(self, task_id: str, metric_name: str) -> float:
        """Read from evaluation.json"""
        return self._read_artifact_metric(task_id, "evaluation.json", metric_name)
    
    def _get_cost_metric(self, task_id: str) -> float:
        """Get total cost for task"""
        cost_path = os.path.join(
            self.artifacts_base, "rag_project", task_id, "cost_report.json"
        )
        
        if not os.path.exists(cost_path):
            return 0.0
        
        try:
            with open(cost_path, "r", encoding="utf-8") as f:
                entries = json.load(f) or []
            return sum(e.get("cost", e.get("estimated_cost", 0)) for e in entries)
        except Exception:
            return 0.0
    
    def _get_latency_metric(self, task_id: str) -> float:
        """Get latency for task"""
        trace_path = os.path.join(
            self.artifacts_base, "rag_project", task_id, "system_trace.json"
        )
        
        if not os.path.exists(trace_path):
            return 0.0
        
        try:
            with open(trace_path, "r", encoding="utf-8") as f:
                trace = json.load(f)
            
            # Sum agent latencies
            executions = trace.get("agent_executions", [])
            total_latency = sum(
                e.get("llm_info", {}).get("latency_ms", 0)
                for e in executions
            )
            return total_latency
        except Exception:
            return 0.0
    
    def _get_success_rate_metric(self, task_id: str) -> float:
        """Get success rate (1.0 if completed, 0.0 otherwise)"""
        manifest_path = os.path.join(
            self.artifacts_base, "rag_project", task_id, "delivery_manifest.json"
        )
        
        if not os.path.exists(manifest_path):
            return 0.0
        
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            return 0.0 if manifest.get("failed", True) else 1.0
        except Exception:
            return 0.0
    
    def _get_quality_metric(self, task_id: str) -> float:
        """Get quality score"""
        eval_path = os.path.join(
            self.artifacts_base, "rag_project", task_id, "evaluation.json"
        )
        
        if not os.path.exists(eval_path):
            return 0.0
        
        try:
            with open(eval_path, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
            return float(eval_data.get("quality_score", 0))
        except Exception:
            return 0.0


class GateExecutor:
    """
    Industrial-grade gate executor with real metric evaluation.
    
    Features:
    - Multi-metric gate evaluation
    - Real data from artifacts
    - Weighted scoring
    - Evidence-based decisions
    """
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.metric_collector = MetricCollector(artifacts_base)
        self.artifacts_base = artifacts_base
    
    def evaluate_gate(
        self,
        gate_name: str,
        task_id: str,
        metric_definitions: List[Dict[str, Any]],
        pass_threshold: float = 0.8
    ) -> GateEvaluationResult:
        """
        Evaluate a gate based on metrics.
        
        Args:
            gate_name: Name of the gate
            task_id: Task to evaluate
            metric_definitions: List of metric definitions
            pass_threshold: Weighted score threshold to pass
            
        Returns:
            GateEvaluationResult
        """
        # Collect metrics
        metrics = self.metric_collector.collect_metrics(task_id, metric_definitions)
        
        # Calculate scores
        total_weight = sum(m.weight for m in metrics)
        weighted_sum = sum(m.weight for m in metrics if m.passed)
        weighted_score = weighted_sum / max(total_weight, 1)
        
        passed_count = sum(1 for m in metrics if m.passed)
        
        # Determine decision
        if weighted_score >= pass_threshold:
            decision = GateDecision.PROMOTE
            reason = f"Gate passed with score {weighted_score:.2f}"
        elif weighted_score >= pass_threshold * 0.7:
            decision = GateDecision.HOLD
            reason = f"Near threshold ({weighted_score:.2f}), collecting more data"
        else:
            decision = GateDecision.BLOCK
            failed_metrics = [m.name for m in metrics if not m.passed]
            reason = f"Gate failed: {', '.join(failed_metrics[:3])}"
        
        result = GateEvaluationResult(
            gate_name=gate_name,
            decision=decision,
            metrics=metrics,
            passed_metrics=passed_count,
            total_metrics=len(metrics),
            weighted_score=weighted_score,
            reason=reason,
            evidence={
                "task_id": task_id,
                "pass_threshold": pass_threshold
            }
        )
        
        # Save evaluation result
        self._save_evaluation(task_id, gate_name, result)
        
        return result
    
    def _save_evaluation(
        self,
        task_id: str,
        gate_name: str,
        result: GateEvaluationResult
    ):
        """Save gate evaluation result"""
        gate_dir = os.path.join(self.artifacts_base, "gates", task_id)
        os.makedirs(gate_dir, exist_ok=True)
        
        gate_path = os.path.join(gate_dir, f"{gate_name}.json")
        with open(gate_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)


def _load_gate_decision(gate_decision_path: str) -> Dict[str, Any]:
    """Load gate decision from file"""
    if not os.path.isfile(gate_decision_path):
        raise NoAuthoritativeGateDecision("No Authoritative GateDecision: missing gate_decision.json")

    with open(gate_decision_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict) or "decision" not in payload:
        raise NoAuthoritativeGateDecision("No Authoritative GateDecision: invalid structure")

    return payload


def execute_gate_decision(
    gate_decision_path: str,
    promote: Callable[[], None] | None = None,
    rollback: Callable[[], None] | None = None,
    block: Callable[[str], None] | None = None,
) -> Dict[str, Any]:
    """Execute a gate decision from file"""
    payload = _load_gate_decision(gate_decision_path)
    decision = str(payload.get("decision"))
    reason = str(payload.get("reason", ""))

    trace: Dict[str, Any] = {
        "gate_decision_path": gate_decision_path,
        "decision": decision,
        "reason": reason,
        "executed_at": datetime.now().isoformat()
    }

    if decision == "promote":
        if promote:
            promote()
        trace["executed_action"] = "promote"
    elif decision == "rollback":
        if rollback:
            rollback()
        trace["executed_action"] = "rollback"
    else:
        if block:
            block(reason)
        trace["executed_action"] = "block"

    return trace


# Singleton gate executor
_gate_executor: Optional[GateExecutor] = None


def get_gate_executor() -> GateExecutor:
    """Get singleton GateExecutor"""
    global _gate_executor
    if _gate_executor is None:
        _gate_executor = GateExecutor()
    return _gate_executor
