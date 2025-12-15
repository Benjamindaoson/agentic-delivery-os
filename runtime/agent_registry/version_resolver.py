"""
Version resolver to check DAG compatibility.
"""
from typing import List
from runtime.agent_registry.agent_spec import AgentSpec


def check_compatibility(agent_specs: List[AgentSpec]) -> bool:
    """
    Ensure no conflicting versions for same agent_id in one DAG.
    """
    seen = {}
    for spec in agent_specs:
        if spec.agent_id in seen and seen[spec.agent_id] != spec.agent_version:
            return False
        seen[spec.agent_id] = spec.agent_version
    return True


