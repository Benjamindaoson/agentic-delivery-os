"""
Delivery Package Builder
Creates auditable delivery package directory.
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any


class DeliveryPackageBuilder:
    def __init__(self, base_dir: str = "artifacts/delivery_packages"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _hash_json(self, obj: Any) -> str:
        return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()

    def build(
        self,
        package_id: str,
        delivery_spec: Dict[str, Any],
        data_manifest: Dict[str, Any],
        index_manifest: Dict[str, Any],
        retrieval_config: Dict[str, Any],
        evaluation_report: Dict[str, Any],
        full_trace: Dict[str, Any],
    ) -> str:
        pkg_dir = os.path.join(self.base_dir, package_id)
        os.makedirs(os.path.join(pkg_dir, "trace"), exist_ok=True)

        def write(name: str, content: Dict[str, Any]):
            path = os.path.join(pkg_dir, name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            return path

        write("delivery_spec.json", delivery_spec)
        write("data_manifest.json", data_manifest)
        write("index_manifest.json", index_manifest)
        write("retrieval_config.json", retrieval_config)
        write("evaluation_report.json", evaluation_report)
        with open(os.path.join(pkg_dir, "trace", "full_trace.json"), "w", encoding="utf-8") as f:
            json.dump(full_trace, f, indent=2, ensure_ascii=False)

        return pkg_dir


builder_singleton = DeliveryPackageBuilder()


