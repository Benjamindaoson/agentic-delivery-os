"""
Execution Admission Layer with artifact output.
"""
import hashlib
import json
import os
from datetime import datetime
from typing import Dict, Any


def _hash_snapshot(snapshot: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()


def decide_admission(task_snapshot: Dict[str, Any], system_constraints: Dict[str, Any]) -> Dict[str, Any]:
    """
    task_snapshot: {task_id, run_id, size, pages, rows, unattended, budget_estimate}
    system_constraints: {max_concurrency, max_size, max_pages, max_rows, allow_unattended}
    """
    decision = "ALLOW"
    reason = "ok"
    checked = {
        "size_ok": task_snapshot.get("size", 0) <= system_constraints.get("max_size", float("inf")),
        "pages_ok": task_snapshot.get("pages", 0) <= system_constraints.get("max_pages", float("inf")),
        "rows_ok": task_snapshot.get("rows", 0) <= system_constraints.get("max_rows", float("inf")),
        "unattended_ok": (not task_snapshot.get("unattended")) or system_constraints.get("allow_unattended", True),
    }
    if not all(checked.values()):
        decision = "REJECT"
        reason = "constraint_violation"

    snapshot_hash = _hash_snapshot({"task": task_snapshot, "constraints": system_constraints, "checked": checked})
    result = {
        "decision": decision,
        "reject_reason": None if decision == "ALLOW" else reason,
        "checked_constraints": checked,
        "system_snapshot_hash": snapshot_hash,
        "timestamp": datetime.now().isoformat(),
    }
    out_dir = os.path.join("artifacts", "execution_control")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "admission_decision.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result

