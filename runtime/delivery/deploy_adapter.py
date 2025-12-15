"""
Deploy Adapter: load delivery bundle and expose runtime pointers.
"""
import json
import hashlib
import os
from typing import Dict, Any


def deploy(bundle_path: str) -> Dict[str, Any]:
    if not os.path.exists(bundle_path):
        raise FileNotFoundError(bundle_path)
    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    if "delivery_bundle_hash" in bundle:
        computed = hashlib.sha256(json.dumps({k: v for k, v in bundle.items() if k != "delivery_bundle_hash"}, sort_keys=True).encode()).hexdigest()
        if computed != bundle["delivery_bundle_hash"]:
            raise ValueError("bundle hash mismatch")
    runtime_config = {
        "corpus_path": bundle.get("corpus_path"),
        "index_path": bundle.get("index_path"),
        "retrieval_config": bundle.get("retrieval_config"),
        "model_routing_config": bundle.get("model_routing_config"),
        "bundle_hash": hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest(),
    }
    out_dir = os.path.join("artifacts", "deployments")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "active_runtime.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(runtime_config, f, indent=2, ensure_ascii=False)
    return runtime_config

