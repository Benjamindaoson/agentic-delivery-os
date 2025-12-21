"""
Policy-as-code governance placeholder.
Provides versioned rule pack interfaces for GovernanceEngine to consume.
"""
from typing import Dict, Any, List

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


