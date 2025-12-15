"""
Common utilities for execution workers.
"""
import os
import json
import hashlib
import time
from typing import Dict, Any

FAIL_TYPES = {
    "TOOL_UNAVAILABLE",
    "FORMAT_MISMATCH",
    "RESOURCE_LIMIT_EXCEEDED",
    "DATA_CORRUPTED",
    "EXECUTION_TIMEOUT",
}


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: Any):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def evidence_record(
    worker_type: str,
    tool_version: str,
    input_obj: Any,
    output_obj: Any,
    status: str,
    failure_type: str = None,
    resource_usage: Dict[str, Any] = None,
    start_time: float = None,
) -> Dict[str, Any]:
    end_time = time.time()
    execution_time_ms = int((end_time - start_time) * 1000) if start_time else 0
    return {
        "worker_type": worker_type,
        "tool_version": tool_version,
        "input_hash": sha256_json(input_obj),
        "output_hash": sha256_json(output_obj) if output_obj is not None else "",
        "execution_time_ms": execution_time_ms,
        "resource_usage": resource_usage or {},
        "status": status,
        "failure_type": failure_type or "",
    }


