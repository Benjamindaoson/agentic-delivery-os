"""
Agent Lifecycle Manager: init / active / deprecated / disabled.
"""
from typing import Dict, Tuple
from runtime.agent_registry.agent_spec import AgentSpec


class LifecycleManager:
    def __init__(self):
        self.states: Dict[Tuple[str, str], str] = {}  # (agent_id, version) -> state
        self.breaks_replay: Dict[Tuple[str, str], bool] = {}

    def set_state(self, spec: AgentSpec, state: str, breaks_replay: bool = False):
        key = (spec.agent_id, spec.agent_version)
        self.states[key] = state
        self.breaks_replay[key] = breaks_replay

    def get_state(self, agent_id: str, version: str) -> str:
        return self.states.get((agent_id, version), "init")

    def can_execute(self, agent_id: str, version: str) -> bool:
        state = self.get_state(agent_id, version)
        return state == "active"

    def is_replay_safe(self, agent_id: str, version: str) -> bool:
        return not self.breaks_replay.get((agent_id, version), False)


lifecycle_manager_singleton = LifecycleManager()


