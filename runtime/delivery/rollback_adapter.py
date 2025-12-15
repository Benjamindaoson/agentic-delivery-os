"""
Rollback Adapter: restore any historical delivery bundle.
"""
import os
import json
import hashlib
from typing import Dict, Any


def rollback(bundle_path: str) -> Dict[str, Any]:
    if not os.path.exists(bundle_path):
        raise FileNotFoundError(bundle_path)
    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    # 对 delivery_bundle_hash 字段进行稳定的哈希校验：计算时排除 hash 字段本身
    canonical_payload = {k: v for k, v in bundle.items() if k != "delivery_bundle_hash"}
    bundle_hash = hashlib.sha256(json.dumps(canonical_payload, sort_keys=True).encode()).hexdigest()
    expected_hash = (
        bundle.get("delivery_bundle_hash")
        or bundle.get("evidence_map", {}).get("delivery_bundle_hash")
        or bundle_hash
    )
    if bundle_hash != expected_hash:
        raise ValueError("hash mismatch")
    out_dir = os.path.join("artifacts", "deployments")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "active_runtime.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
    return {"status": "restored", "bundle_hash": bundle_hash, "path": bundle_path}

