from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import yaml


EVAL_SIGNAL_PATH = os.path.join("artifacts", "eval_learning_signals.json")
RELEASE_GATE_CFG = os.path.join("configs", "release_gate.yaml")


def _load_gate_thresholds() -> Dict[str, Any]:
    if not os.path.exists(RELEASE_GATE_CFG):
        # Safe defaults matching previous config
        return {
            "offline": {"ocr_coverage_min": 0.85, "table_recovery_f1_min": 0.80},
            "online": {
                "retrieval_recall_at_5_min": 0.85,
                "generation_faithfulness_min": 0.90,
                "refusal_correct_refusal_rate_min": 0.95,
            },
        }
    with open(RELEASE_GATE_CFG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("gate", {})


def generate_eval_signals(eval_report: Dict[str, Any], coverage_matrix: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate structured learning signals based on eval report + coverage.

    At least implement:
    - numeric_mismatch_rate > threshold
    - retrieval_recall < gate
    - hitl_fix_rate < threshold
    """
    metrics: Dict[str, Any] = eval_report.get("metrics", {})
    gate_cfg = _load_gate_thresholds()

    signals: List[Dict[str, Any]] = []

    # numeric_mismatch_rate > threshold (default threshold 0.10)
    numeric_metrics = metrics.get("online", {}).get("numeric", {})
    numeric_rate = numeric_metrics.get("numeric_mismatch_rate")
    numeric_threshold = numeric_metrics.get("numeric_mismatch_threshold", 0.10)
    if isinstance(numeric_rate, (int, float)) and numeric_rate > numeric_threshold:
        signals.append(
            {
                "type": "numeric_mismatch_rate_high",
                "value": float(numeric_rate),
                "threshold": float(numeric_threshold),
                "action_hint": "increase_numeric_first_weight",
            }
        )

    # retrieval_recall < gate
    retrieval_metrics = metrics.get("online", {}).get("retrieval", {})
    recall_at_5 = retrieval_metrics.get("recall@5")
    recall_gate = gate_cfg.get("online", {}).get("retrieval_recall_at_5_min", 0.85)
    if isinstance(recall_at_5, (int, float)) and recall_at_5 < recall_gate:
        signals.append(
            {
                "type": "retrieval_recall_low",
                "value": float(recall_at_5),
                "threshold": float(recall_gate),
                "action_hint": "increase_hybrid_weight",
            }
        )

    # hitl_fix_rate < threshold (default threshold 0.2)
    hitl_metrics = metrics.get("hitl", {})
    fix_rate = hitl_metrics.get("fix_rate")
    fix_threshold = hitl_metrics.get("fix_rate_threshold", 0.2)
    if isinstance(fix_rate, (int, float)) and fix_rate < fix_threshold:
        signals.append(
            {
                "type": "hitl_fix_rate_low",
                "value": float(fix_rate),
                "threshold": float(fix_threshold),
                "action_hint": "improve_offline_quality_or_routing",
            }
        )

    result = {"signals": signals}

    os.makedirs(os.path.dirname(EVAL_SIGNAL_PATH), exist_ok=True)
    with open(EVAL_SIGNAL_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result
































