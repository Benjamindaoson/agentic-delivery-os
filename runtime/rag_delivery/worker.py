"""
RAG Delivery Worker: freeze decided outputs into delivery artifacts.
Deterministic; no strategy selection, no semantics.
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any


def _hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def build_delivery(run_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload must include:
    - delivery_spec
    - data_manifest
    - chunking_strategy
    - retrieval_config
    - model_routing_config
    """
    required_keys = [
        "delivery_spec",
        "data_manifest",
        "chunking_strategy",
        "retrieval_config",
        "model_routing_config",
    ]
    for k in required_keys:
        if k not in payload:
            raise ValueError(f"missing {k}")

    base_dir = os.path.join("artifacts", "rag_delivery", run_id)
    corpus_dir = os.path.join(base_dir, "corpus")
    index_dir = os.path.join(base_dir, "index")
    os.makedirs(corpus_dir, exist_ok=True)
    os.makedirs(index_dir, exist_ok=True)

    # corpus: dump data manifest as structured corpus placeholder
    corpus = {
        "files": payload["data_manifest"].get("files", []),
        "metadata": {"created_at": datetime.now().isoformat()},
    }
    with open(os.path.join(corpus_dir, "corpus.json"), "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)

    chunking_manifest_path = os.path.join(base_dir, "chunking_manifest.json")
    with open(chunking_manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload["chunking_strategy"], f, indent=2, ensure_ascii=False)

    retrieval_path = os.path.join(base_dir, "retrieval_config.json")
    with open(retrieval_path, "w", encoding="utf-8") as f:
        json.dump(payload["retrieval_config"], f, indent=2, ensure_ascii=False)

    model_route_path = os.path.join(base_dir, "model_routing_config.json")
    with open(model_route_path, "w", encoding="utf-8") as f:
        json.dump(payload["model_routing_config"], f, indent=2, ensure_ascii=False)

    evidence_map = {
        "data_manifest_hash": _hash(payload["data_manifest"]),
        "chunking_strategy_hash": _hash(payload["chunking_strategy"]),
        "retrieval_config_hash": _hash(payload["retrieval_config"]),
        "model_routing_hash": _hash(payload["model_routing_config"]),
    }
    with open(os.path.join(base_dir, "evidence_map.json"), "w", encoding="utf-8") as f:
        json.dump(evidence_map, f, indent=2, ensure_ascii=False)

    # index manifests placeholders
    vector_manifest = {"status": "not_built", "hash": _hash({"empty": True})}
    bm25_manifest = {"status": "not_built", "hash": _hash({"empty": True})}
    with open(os.path.join(index_dir, "vector_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(vector_manifest, f, indent=2, ensure_ascii=False)
    with open(os.path.join(index_dir, "bm25_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(bm25_manifest, f, indent=2, ensure_ascii=False)

    delivery_bundle = {
        "delivery_spec": payload["delivery_spec"],
        "corpus_path": corpus_dir,
        "chunking_manifest": chunking_manifest_path,
        "index_path": index_dir,
        "retrieval_config": payload["retrieval_config"],
        "model_routing_config": payload["model_routing_config"],
        "evidence_map": evidence_map,
        "created_at": datetime.now().isoformat(),
    }
    delivery_bundle_path = os.path.join(base_dir, "delivery_bundle.json")
    with open(delivery_bundle_path, "w", encoding="utf-8") as f:
        json.dump(delivery_bundle, f, indent=2, ensure_ascii=False)

    hashes = {
        "corpus_hash": _hash(corpus),
        "chunking_manifest_hash": _hash(payload["chunking_strategy"]),
        "retrieval_hash": _hash(payload["retrieval_config"]),
        "model_routing_hash": _hash(payload["model_routing_config"]),
        "delivery_bundle_hash": _hash(delivery_bundle),
        "evidence_hash": _hash(evidence_map),
    }
    with open(os.path.join(base_dir, "hashes.json"), "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)

    return {
        "delivery_bundle_path": delivery_bundle_path,
        "hashes": hashes,
    }


