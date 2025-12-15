"""
Compatibility checker: reject incompatible versions in the same graph.
"""
from typing import List
from runtime.agent_registry.agent_spec import AgentSpec
from runtime.agent_registry import version_resolver
from runtime.agent_lifecycle.lifecycle_manager import lifecycle_manager_singleton


def check(agent_specs: List[AgentSpec]) -> bool:
    # version uniqueness
    if not version_resolver.check_compatibility(agent_specs):
        return False
    # no deprecated/disabled unless explicitly allowed
    for spec in agent_specs:
        state = lifecycle_manager_singleton.get_state(spec.agent_id, spec.agent_version)
        if state in ["deprecated", "disabled"]:
            return False
    return True


