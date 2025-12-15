"""
Execution Worker Capability Manifest and checks.
"""
from typing import Dict, Any
import json
import hashlib

CAPABILITY_MANIFEST = {
    "ocr_worker": {
        "supported_inputs": ["pdf_scan", "image"],
        "constraints": {"max_pages": 500, "max_file_size_mb": 200},
        "performance_profile": {"avg_latency_ms": 1200, "p95_latency_ms": 2600},
        "cost_profile": {"unit": "page", "cost_per_unit": 0.003},
        "deterministic": True,
        "fallback_supported": False,
    },
    "parsing_worker": {
        "supported_inputs": ["pdf_text", "docx", "html", "xlsx", "csv"],
        "constraints": {"max_file_size_mb": 500},
        "performance_profile": {"avg_latency_ms": 600, "p95_latency_ms": 1500},
        "cost_profile": {"unit": "page", "cost_per_unit": 0.001},
        "deterministic": True,
        "fallback_supported": False,
    },
    "chunking_worker": {
        "supported_inputs": ["structured_blocks"],
        "constraints": {"max_chunks": 100000},
        "performance_profile": {"avg_latency_ms": 400, "p95_latency_ms": 900},
        "cost_profile": {"unit": "chunk", "cost_per_unit": 0.0001},
        "deterministic": True,
        "fallback_supported": False,
    },
    "embedding_worker": {
        "supported_inputs": ["chunks"],
        "constraints": {"max_chunks": 50000},
        "performance_profile": {"avg_latency_ms": 800, "p95_latency_ms": 1800},
        "cost_profile": {"unit": "chunk", "cost_per_unit": 0.0005},
        "deterministic": True,
        "fallback_supported": False,
    },
}


def capability_hash() -> str:
    return hashlib.sha256(json.dumps(CAPABILITY_MANIFEST, sort_keys=True).encode()).hexdigest()


def check_capability(worker_id: str, input_meta: Dict[str, Any]) -> bool:
    cap = CAPABILITY_MANIFEST.get(worker_id)
    if not cap:
        return False
    if "max_file_size_mb" in cap.get("constraints", {}):
        if (input_meta.get("size", 0) / 1_000_000) > cap["constraints"]["max_file_size_mb"]:
            return False
    return True


