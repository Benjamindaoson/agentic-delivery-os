"""
Policy packager: bundle candidate artifacts with config hash for replay.
Artifacts: artifacts/policy/candidates/{candidate_id}.json
"""
import os
import json
from typing import Dict, Any
from datetime import datetime
from runtime.artifacts.artifact_schema import compute_inputs_hash, DEFAULT_SCHEMA_VERSION


class PolicyPackager:
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.candidates_dir = os.path.join(artifacts_dir, "policy", "candidates")
        os.makedirs(self.candidates_dir, exist_ok=True)

    def package(self, candidate_id: str, payload: Dict[str, Any]) -> str:
        payload = dict(payload)
        payload.setdefault("schema_version", DEFAULT_SCHEMA_VERSION)
        payload.setdefault("timestamp", datetime.now().isoformat())
        payload["inputs_hash"] = compute_inputs_hash(payload)
        path = os.path.join(self.candidates_dir, f"{candidate_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path



