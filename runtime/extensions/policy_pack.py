"""
Policy-as-code governance placeholder.
Provides versioned rule pack interfaces for GovernanceEngine to consume.
"""
import os
import json
from typing import Dict, Any, List, Optional

class PolicyPack:
    def __init__(self, pack_id: str, version: str, rules: List[Dict[str, Any]]):
        self.pack_id = pack_id
        self.version = version
        self.rules = rules

class PolicyRegistry:
    def __init__(self):
        self.packs = {}

    def register(self, pack: PolicyPack):
        self.packs[f"{pack.pack_id}:{pack.version}"] = pack

    def get(self, pack_id: str, version: str = None) -> PolicyPack:
        if version:
            return self.packs.get(f"{pack_id}:{version}")
        # return latest if exists
        matches = [p for k, p in self.packs.items() if k.startswith(f"{pack_id}:")]
        return matches[-1] if matches else None


def load_policy_artifact(path: str) -> Dict[str, Any]:
    """
    从文件路径加载 policy artifact。
    
    Args:
        path: policy artifact JSON 文件路径
        
    Returns:
        policy artifact dict
        
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Policy artifact not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        policy = json.load(f)
    
    return policy

