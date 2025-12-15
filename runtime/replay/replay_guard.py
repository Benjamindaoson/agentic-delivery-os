"""
Replay guard: ensure bit-for-bit replay given same inputs/policies/versions.
"""
import hashlib
import json
from typing import Dict, Any


def compute_replay_key(agent_version: str, inputs: Dict[str, Any], policies: Dict[str, Any]) -> str:
    payload = {
        "agent_version": agent_version,
        "inputs": inputs,
        "policies": policies,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


