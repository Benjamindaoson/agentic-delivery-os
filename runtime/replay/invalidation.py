"""
Replay invalidation marker for agent upgrades.
"""
from typing import Dict, Any


class ReplayInvalidation:
    def __init__(self):
        self.invalidated = {}  # (agent_id, version) -> reason

    def mark(self, agent_id: str, version: str, reason: str):
        self.invalidated[(agent_id, version)] = reason

    def is_invalidated(self, agent_id: str, version: str) -> bool:
        return (agent_id, version) in self.invalidated


replay_invalidation_singleton = ReplayInvalidation()


