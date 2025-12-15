"""
Strategy Template Registry: tracks deprecated/stable paths.
"""
import os
import json
from typing import Dict, Any


class StrategyRegistry:
    def __init__(self, base_dir: str = "artifacts/strategy_templates"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.registry_path = os.path.join(base_dir, "registry.json")
        if not os.path.exists(self.registry_path):
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump({"deprecated": [], "preferred": [], "conditional_preference": []}, f)

    def update(self, deprecated: list, preferred: list, conditional_preference: list = None):
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "deprecated": deprecated,
                    "preferred": preferred,
                    "conditional_preference": conditional_preference or [],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def load(self) -> Dict[str, Any]:
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)


strategy_registry_singleton = StrategyRegistry()

