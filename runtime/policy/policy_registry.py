"""
Lightweight policy registry to track active/candidate/shadow states.
Artifacts: artifacts/policy/registry.json
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional


class PolicyRegistry:
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.registry_path = os.path.join(artifacts_dir, "policy", "registry.json")
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"schema_version": "1.0", "active": None, "shadow": [], "candidates": [], "timestamp": datetime.now().isoformat()}

    def save(self) -> None:
        self.state["timestamp"] = datetime.now().isoformat()
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def set_active(self, policy_id: str) -> None:
        self.state["active"] = policy_id
        self.save()

    def add_candidate(self, candidate_id: str) -> None:
        if candidate_id not in self.state["candidates"]:
            self.state["candidates"].append(candidate_id)
        self.save()

    def add_shadow(self, candidate_id: str) -> None:
        if candidate_id not in self.state["shadow"]:
            self.state["shadow"].append(candidate_id)
        self.save()

    def mark_rejected(self, candidate_id: str) -> None:
        self.state["shadow"] = [c for c in self.state["shadow"] if c != candidate_id]
        self.state["candidates"] = [c for c in self.state["candidates"] if c != candidate_id]
        self.save()



