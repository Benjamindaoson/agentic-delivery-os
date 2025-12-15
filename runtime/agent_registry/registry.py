"""
Agent Registry: registration and lookup with contract validation.
"""
from typing import Dict, Tuple
from runtime.agent_registry.agent_spec import AgentSpec


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[Tuple[str, str], AgentSpec] = {}

    def register(self, spec: AgentSpec):
        key = (spec.agent_id, spec.agent_version)
        self._agents[key] = spec

    def get(self, agent_id: str, version: str) -> AgentSpec:
        return self._agents.get((agent_id, version))

    def validate_contract(self, agent: AgentSpec, input_schema_hash: str, output_schema_hash: str) -> bool:
        contract = agent.agent_contract
        return contract.input_schema_hash == input_schema_hash and contract.output_schema_hash == output_schema_hash

    def all(self):
        return list(self._agents.values())


registry_singleton = AgentRegistry()


