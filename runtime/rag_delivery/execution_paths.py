"""
Execution paths definitions for replayable alternatives.
"""
from typing import Dict, Any
import os
import json
from datetime import datetime

PATHS = {
    "FULL_RAG_PATH": {
        "description": "Full RAG with indexing and retrieval",
        "artifacts": ["corpus", "chunks", "index", "retrieval", "trust"],
        "entry_condition": "default",
    },
    "FAST_PATH_NO_INDEX": {
        "description": "Fast path without indexing",
        "artifacts": ["corpus", "chunks", "retrieval"],
        "entry_condition": "low_latency",
    },
    "RAG_ONLY_PATCH_PATH": {
        "description": "Patch-only RAG without rebuild",
        "artifacts": ["patch_corpus", "patch_retrieval"],
        "entry_condition": "patch_mode",
    },
}


def record_path(run_id: str, path_id: str, reason: str) -> str:
    if path_id not in PATHS:
        raise ValueError("invalid path_id")
    out = {
        "path_id": path_id,
        "reason": reason,
        "path_def": PATHS[path_id],
        "timestamp": datetime.now().isoformat(),
    }
    base = os.path.join("artifacts", "rag_delivery", run_id)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "path_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


