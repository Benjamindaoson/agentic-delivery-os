"""
DQ Regression Guard (Phase 8 · P4-1)

Responsible for detecting regressions in DQ metrics for the same data source.
This module is deliberately not wired into the main pipeline yet.
"""
from __future__ import annotations

from typing import Dict, Any, List


METRIC_NAMES = [
    "ocr_coverage",
    "table_recovery_f1",
    "empty_page_ratio",
    "duplicate_page_ratio",
]


def check_dq_regression(
    current_dq: dict,
    previous_dq: dict | None,
) -> dict:
    """
    Compare current and previous DQ reports and detect regressions.

    Rules (hard-coded):
    - coverage / f1 metrics: regression if current < previous
    - ratio metrics: regression if current > previous
    - previous_dq is None → PASS (no regression)
    """
    if previous_dq is None:
        return {"regression_detected": False, "failed_metrics": []}

    current_metrics: Dict[str, Any] = (current_dq or {}).get("metrics", {})
    previous_metrics: Dict[str, Any] = (previous_dq or {}).get("metrics", {})

    failed: List[str] = []

    # coverage / f1: higher is better
    for name in ("ocr_coverage", "table_recovery_f1"):
        if name in current_metrics and name in previous_metrics:
            try:
                cur = float(current_metrics[name])
                prev = float(previous_metrics[name])
            except (TypeError, ValueError):
                continue
            if cur < prev:
                failed.append(name)

    # ratios: lower is better
    for name in ("empty_page_ratio", "duplicate_page_ratio"):
        if name in current_metrics and name in previous_metrics:
            try:
                cur = float(current_metrics[name])
                prev = float(previous_metrics[name])
            except (TypeError, ValueError):
                continue
            if cur > prev:
                failed.append(name)

    return {
        "regression_detected": bool(failed),
        "failed_metrics": failed,
    }
































