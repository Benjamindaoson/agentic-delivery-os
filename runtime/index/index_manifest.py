"""
Index / Chunk / Retrieval versioning and rollback support.
"""
import hashlib
import json
from typing import Dict, Any


def build_index_manifest(chunk_strategy: str, embedding_model: str, bm25: bool) -> Dict[str, Any]:
    manifest = {
        "chunk_strategy": chunk_strategy,
        "embedding_model": embedding_model,
        "bm25": bm25,
        "version": "v1",
    }
    manifest["hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return manifest


