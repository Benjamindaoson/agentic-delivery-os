"""
Aggregate metrics across agents.
"""
from typing import Dict, Any
import json
import os


def aggregate(base_dir: str = "artifacts/metrics") -> Dict[str, Any]:
    agg = {}
    if not os.path.exists(base_dir):
        return agg
    for fname in os.listdir(base_dir):
        if fname.endswith(".json"):
            with open(os.path.join(base_dir, fname), "r", encoding="utf-8") as f:
                agg[fname.replace(".json", "")] = json.load(f)
    return agg


