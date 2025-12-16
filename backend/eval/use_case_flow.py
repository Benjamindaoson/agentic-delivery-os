from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .coverage_matrix import build_coverage_matrix
from .use_case_runner import evaluate_use_cases


@dataclass
class EvalReport:
    run_id: str
    results: Dict[str, str]
    metrics: Dict[str, Any]
    coverage_matrix: Dict[str, Any]
    status: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningSignal:
    run_id: str
    signals: List[Dict[str, Any]]
    source: str
    eval_status: str
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateDecision:
    run_id: str
    decision: str
    reason: str
    summary: Dict[str, Any]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist_json(path: str, payload: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def _persist_jsonl(path: str, payload: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _build_eval_report(run_id: str, results: Dict[str, str]) -> EvalReport:
    total = len(results)
    failed = [name for name, state in results.items() if state != "pass"]
    passed = total - len(failed)
    pass_rate = (passed / total) if total else 1.0
    status = "pass" if not failed else "fail"
    metrics = {
        "use_case": {
            "total": total,
            "passed": passed,
            "failed": len(failed),
            "pass_rate": pass_rate,
        }
    }
    coverage = build_coverage_matrix({"metrics": metrics})
    return EvalReport(
        run_id=run_id,
        results=results,
        metrics=metrics,
        coverage_matrix=coverage,
        status=status,
        generated_at=_utc_now(),
    )


def _build_learning_signal(eval_report: EvalReport) -> LearningSignal:
    failed = [name for name, state in eval_report.results.items() if state != "pass"]
    signals: List[Dict[str, Any]] = []
    if failed:
        for scenario in failed:
            signals.append(
                {
                    "type": "use_case_failed",
                    "scenario": scenario,
                    "action_hint": "improve_prompt_or_rules",
                    "status": eval_report.status,
                }
            )
    return LearningSignal(
        run_id=eval_report.run_id,
        signals=signals,
        source="use_case_eval",
        eval_status=eval_report.status,
        generated_at=_utc_now(),
    )


def _decide_gate(eval_report: EvalReport) -> GateDecision:
    failed_count = eval_report.metrics.get("use_case", {}).get("failed", 0)
    decision = "promote" if failed_count == 0 else "rollback"
    reason = "All use cases passed" if decision == "promote" else "Use case failures detected"
    summary = {
        "pass_rate": eval_report.metrics.get("use_case", {}).get("pass_rate"),
        "failed": failed_count,
        "total": eval_report.metrics.get("use_case", {}).get("total"),
    }
    return GateDecision(
        run_id=eval_report.run_id,
        decision=decision,
        reason=reason,
        summary=summary,
        generated_at=_utc_now(),
    )


def run_use_case_flow(
    answer_bundle: Dict[str, Any],
    run_id: str | None = None,
    artifacts_root: str = os.path.join("artifacts", "runs"),
) -> Tuple[EvalReport, LearningSignal, GateDecision]:
    """
    Execute the use-case -> eval -> learning -> gate loop.

    Returns the structured EvalReport, LearningSignal, and GateDecision instances.
    """
    current_run_id = run_id or str(uuid.uuid4())
    base_dir = os.path.join(artifacts_root, current_run_id)
    trace: List[Dict[str, Any]] = []

    trace.append({"step": "evaluate_use_cases", "status": "started", "timestamp": _utc_now()})
    results = evaluate_use_cases(answer_bundle)
    trace.append(
        {
            "step": "evaluate_use_cases",
            "status": "completed",
            "timestamp": _utc_now(),
            "details": {"total": len(results)},
        }
    )

    eval_report = _build_eval_report(current_run_id, results)
    eval_report_path = os.path.join(base_dir, "eval_report.json")
    _persist_json(eval_report_path, eval_report.to_dict())

    learning_signal = _build_learning_signal(eval_report)
    learning_signal_path = os.path.join(base_dir, "learning_signal.jsonl")
    _persist_jsonl(learning_signal_path, learning_signal.to_dict())

    trace.append(
        {
            "step": "learning_signal",
            "status": "completed",
            "timestamp": _utc_now(),
            "details": {"signal_count": len(learning_signal.signals)},
        }
    )

    gate_decision = _decide_gate(eval_report)
    gate_decision_path = os.path.join(base_dir, "gate_decision.json")
    _persist_json(gate_decision_path, gate_decision.to_dict())

    trace.append(
        {
            "step": "gate_decision",
            "status": "completed",
            "timestamp": _utc_now(),
            "details": gate_decision.summary,
        }
    )

    # persist run trace last
    trace_path = os.path.join(base_dir, "run_trace.json")
    _persist_json(trace_path, {"run_id": current_run_id, "trace": trace})

    return eval_report, learning_signal, gate_decision
