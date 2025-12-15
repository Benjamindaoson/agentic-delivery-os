"""
Scheduling guard before worker invocation.
"""
from typing import Dict, Any


def check_schedule(task_snapshot: Dict[str, Any], capability: Dict[str, Any]) -> Dict[str, Any]:
    """
    task_snapshot: {worker_id, size, path, unattended}
    capability: {unsupported_inputs, supported_execution_paths}
    """
    worker_id = task_snapshot.get("worker_id")
    path = task_snapshot.get("execution_path")
    unsupported = capability.get("unsupported_inputs", [])
    if task_snapshot.get("input_type") in unsupported:
        return {"allowed": False, "reason": "unsupported_input"}
    if path and path not in capability.get("supported_execution_paths", []):
        return {"allowed": False, "reason": "path_not_supported"}
    return {"allowed": True, "reason": "ok"}


