"""
Agent specification model for registration and contract validation.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import hashlib
import json


@dataclass
class AgentContract:
    input_schema_hash: str
    output_schema_hash: str
    failure_modes: List[str]
    timeout_policy: Dict[str, Any]
    idempotency: bool

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass
class AgentSpec:
    agent_id: str
    agent_version: str  # semver
    agent_role: str  # Intent | Data | Retrieval | Eval | Audit | Orchestrator
    agent_contract: AgentContract
    status: str = "init"  # init | active | deprecated | disabled

    def spec_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


