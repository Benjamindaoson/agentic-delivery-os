"""
Runtime Drift Guard: monitors drift metrics and enforces path downgrade.
"""
import os
import json
from typing import Dict, Any
from datetime import datetime


def check_drift(metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    metrics: {evidence_fail_rate, rollback_frequency, fast_path_ratio, repeated_failure_pattern_rate}
    """
    actions = []
    if metrics.get("evidence_fail_rate", 0) > 0.2:
        actions.append("FORCE_DOWNGRADE")
    if metrics.get("rollback_frequency", 0) > 0.1:
        actions.append("DISABLE_FULL_PATH")
    if metrics.get("repeated_failure_pattern_rate", 0) > 0.15:
        actions.append("FORCE_PATCH_PATH")

    result = {
        "metrics": metrics,
        "actions": actions,
        "timestamp": datetime.now().isoformat(),
    }
    out_dir = os.path.join("artifacts", "monitoring")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "runtime_drift_guard.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


