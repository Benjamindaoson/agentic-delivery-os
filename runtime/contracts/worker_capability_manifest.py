"""
Worker Capability Manifest: declarative capability contract for workers.
Produces artifacts/contracts/worker_capability_manifest.json
"""
import os
import json
import hashlib
from typing import Dict, Any, List
from datetime import datetime


DEFAULT_MANIFEST = {
    "workers": [
        {
            "worker_id": "ocr_worker",
            "supported_execution_paths": ["FULL", "FAST", "PATCH"],
            "unsupported_inputs": ["text_only"],
            "resource_profile": {"cpu": "medium", "memory": "medium", "io": "medium"},
            "latency_class": "ASYNC",
            "failure_modes": {"recoverable": ["TOOL_UNAVAILABLE", "EXECUTION_TIMEOUT"], "non_recoverable": ["FORMAT_MISMATCH", "DATA_CORRUPTED"]},
            "sla_expectation": "best-effort",
        },
        {
            "worker_id": "parsing_worker",
            "supported_execution_paths": ["FULL", "FAST", "PATCH"],
            "unsupported_inputs": ["scanned_image_only"],
            "resource_profile": {"cpu": "low", "memory": "medium", "io": "medium"},
            "latency_class": "SYNC",
            "failure_modes": {"recoverable": ["EXECUTION_TIMEOUT"], "non_recoverable": ["FORMAT_MISMATCH"]},
            "sla_expectation": "guaranteed",
        },
        {
            "worker_id": "chunking_worker",
            "supported_execution_paths": ["FULL", "FAST", "PATCH"],
            "unsupported_inputs": [],
            "resource_profile": {"cpu": "low", "memory": "low", "io": "low"},
            "latency_class": "SYNC",
            "failure_modes": {"recoverable": ["EXECUTION_TIMEOUT"], "non_recoverable": ["DATA_CORRUPTED"]},
            "sla_expectation": "guaranteed",
        },
        {
            "worker_id": "embedding_worker",
            "supported_execution_paths": ["FULL", "FAST"],
            "unsupported_inputs": ["patch_only"],
            "resource_profile": {"cpu": "medium", "memory": "medium", "io": "medium"},
            "latency_class": "ASYNC",
            "failure_modes": {"recoverable": ["TOOL_UNAVAILABLE", "EXECUTION_TIMEOUT"], "non_recoverable": ["FORMAT_MISMATCH"]},
            "sla_expectation": "best-effort",
        },
    ],
    "generated_at": "",
    "manifest_hash": "",
}


def _hash_manifest(manifest: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def generate_manifest(custom: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest = DEFAULT_MANIFEST.copy()
    if custom is not None:
        manifest["workers"] = custom
    manifest["generated_at"] = datetime.now().isoformat()
    manifest["manifest_hash"] = _hash_manifest(manifest)
    out_dir = os.path.join("artifacts", "contracts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "worker_capability_manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest


