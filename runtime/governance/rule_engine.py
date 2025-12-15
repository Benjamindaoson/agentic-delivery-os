"""
Rule engine for evaluation → governance actions.
"""
from typing import Dict, Any
from runtime.agent_lifecycle.lifecycle_manager import lifecycle_manager_singleton


def evaluate_and_act(agent_id: str, agent_version: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    actions = []
    failure_rate = metrics.get("failure_type_distribution", {}).get("TOTAL", 0)
    success_rate = metrics.get("success_rate", 1.0)
    if failure_rate > 0.2 or success_rate < 0.8:
        actions.append("throttle")
    if metrics.get("accuracy_drop", False):
        actions.append("rollback")
        lifecycle_manager_singleton.set_state(
            type("S", (), {"agent_id": agent_id, "agent_version": agent_version})(),
            "deprecated",
            breaks_replay=True,
        )
    return {"actions": actions}


