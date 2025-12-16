import json
from pathlib import Path

import pytest

from backend.governance.gate_executor import (
    NoAuthoritativeGateDecision,
    execute_gate_decision,
)


def test_missing_gate_decision_fails(tmp_path):
    gate_path = Path(tmp_path) / "gate_decision.json"
    with pytest.raises(NoAuthoritativeGateDecision):
        execute_gate_decision(str(gate_path))


def test_execute_gate_decision_without_eval_context(tmp_path):
    gate_path = Path(tmp_path) / "gate_decision.json"
    gate_payload = {"decision": "rollback", "reason": "forced"}
    gate_path.write_text(json.dumps(gate_payload), encoding="utf-8")

    called = {"rollback": False, "promote": False, "block_reason": None}

    def record_rollback():
        called["rollback"] = True

    def record_block(reason: str):
        called["block_reason"] = reason

    trace = execute_gate_decision(
        str(gate_path), promote=lambda: called.__setitem__("promote", True), rollback=record_rollback, block=record_block
    )

    assert called["rollback"] is True
    assert called["promote"] is False
    assert called["block_reason"] is None
    assert trace["executed_action"] == "rollback"
