"""
Failure Taxonomy → Recovery Policy Mapping.
"""
from typing import Dict, Any

FAILURE_MAP = {
    "TOOL_UNAVAILABLE": {"severity": "recoverable", "action": "delay_or_switch", "requires_human": False},
    "FORMAT_MISMATCH": {"severity": "terminal", "action": "stop", "requires_human": True},
    "RESOURCE_LIMIT_EXCEEDED": {"severity": "recoverable", "action": "delay", "requires_human": False},
    "DATA_CORRUPTED": {"severity": "terminal", "action": "stop", "requires_human": True},
    "EXECUTION_TIMEOUT": {"severity": "recoverable", "action": "delay_or_switch", "requires_human": False},
}


def map_failure(failure_type: str) -> Dict[str, Any]:
    policy = FAILURE_MAP.get(failure_type, {"severity": "terminal", "action": "stop", "requires_human": True})
    return {
        "failure_type": failure_type,
        "policy": policy,
    }


