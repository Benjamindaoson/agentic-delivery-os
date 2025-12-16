from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .coverage_matrix import build_coverage_matrix
from .use_case_runner import evaluate_use_cases


SEVERITY_ORDER = {"LOW": 0, "MED": 1, "HIGH": 2, "CRITICAL": 3}


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
    signal_id: str
    run_id: str
    signals: List[Dict[str, Any]]
    source: str
    eval_status: str
    severity: str
    recommended_action: str
    consumed: bool
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "LearningSignal":
        return LearningSignal(
            signal_id=payload.get("signal_id", ""),
            run_id=payload.get("run_id", ""),
            signals=payload.get("signals") or [],
            source=payload.get("source", ""),
            eval_status=payload.get("eval_status", ""),
            severity=payload.get("severity", "LOW"),
            recommended_action=payload.get("recommended_action", ""),
            consumed=bool(payload.get("consumed", False)),
            generated_at=payload.get("generated_at", ""),
        )


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


def _severity_rank(severity: str) -> int:
    return SEVERITY_ORDER.get((severity or "").upper(), 0)


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


def load_pending_learning_signals(artifacts_root: str = os.path.join("artifacts", "runs")) -> List[LearningSignal]:
    pending: List[LearningSignal] = []
    if not os.path.isdir(artifacts_root):
        return pending

    for run_id in sorted(os.listdir(artifacts_root)):
        path = os.path.join(artifacts_root, run_id, "learning_signal.jsonl")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                signal = LearningSignal.from_dict(record)
                if not signal.consumed:
                    pending.append(signal)

    pending.sort(key=lambda s: s.generated_at or "")
    return pending


def mark_learning_signal_consumed(
    signal_id: str, artifacts_root: str = os.path.join("artifacts", "runs")
) -> bool:
    if not os.path.isdir(artifacts_root):
        return False

    updated = False
    for run_id in sorted(os.listdir(artifacts_root)):
        path = os.path.join(artifacts_root, run_id, "learning_signal.jsonl")
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]

        new_lines = []
        for line in lines:
            record = json.loads(line)
            if record.get("signal_id") == signal_id:
                record["consumed"] = True
                updated = True
            new_lines.append(json.dumps(record, ensure_ascii=False))

        if updated:
            with open(path, "w", encoding="utf-8") as f:
                for line in new_lines:
                    f.write(line + "\n")
            break

    return updated


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
    severity = "HIGH" if failed else "LOW"
    recommended_action = "rollback_and_fix" if failed else "monitor"
    return LearningSignal(
        signal_id=str(uuid.uuid4()),
        run_id=eval_report.run_id,
        signals=signals,
        source="use_case_eval",
        eval_status=eval_report.status,
        severity=severity,
        recommended_action=recommended_action,
        consumed=False,
        generated_at=_utc_now(),
    )


def _decide_gate(eval_report: EvalReport, pending_learning: List[LearningSignal]) -> GateDecision:
    blocking_signals = [
        signal
        for signal in pending_learning
        if not signal.consumed and _severity_rank(signal.severity) >= _severity_rank("MED")
    ]

    if blocking_signals:
        summary = {
            "blocking_signal_ids": [s.signal_id for s in blocking_signals],
            "blocking_runs": [s.run_id for s in blocking_signals],
        }
        return GateDecision(
            run_id=eval_report.run_id,
            decision="blocked",
            reason="Unconsumed learning signal",
            summary=summary,
            generated_at=_utc_now(),
        )

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

    pending_learning = load_pending_learning_signals(artifacts_root)
    trace.append(
        {
            "step": "load_pending_learning_signals",
            "status": "completed",
            "timestamp": _utc_now(),
            "details": {"pending_count": len(pending_learning)},
        }
    )

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

    gate_decision = _decide_gate(eval_report, pending_learning)
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
