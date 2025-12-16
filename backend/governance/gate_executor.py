from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict


class NoAuthoritativeGateDecision(RuntimeError):
    """Raised when gate_decision.json is missing or malformed."""


def _load_gate_decision(gate_decision_path: str) -> Dict[str, Any]:
    if not os.path.isfile(gate_decision_path):
        raise NoAuthoritativeGateDecision("No Authoritative GateDecision: missing gate_decision.json")

    with open(gate_decision_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict) or "decision" not in payload:
        raise NoAuthoritativeGateDecision("No Authoritative GateDecision: invalid structure")

    return payload


def execute_gate_decision(
    gate_decision_path: str,
    promote: Callable[[], None] | None = None,
    rollback: Callable[[], None] | None = None,
    block: Callable[[str], None] | None = None,
) -> Dict[str, Any]:
    payload = _load_gate_decision(gate_decision_path)
    decision = str(payload.get("decision"))
    reason = str(payload.get("reason", ""))

    trace: Dict[str, Any] = {
        "gate_decision_path": gate_decision_path,
        "decision": decision,
        "reason": reason,
    }

    if decision == "promote":
        if promote:
            promote()
        trace["executed_action"] = "promote"
    elif decision == "rollback":
        if rollback:
            rollback()
        trace["executed_action"] = "rollback"
    else:
        if block:
            block(reason)
        trace["executed_action"] = "block"

    return trace
