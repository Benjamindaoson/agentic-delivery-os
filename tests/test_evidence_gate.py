import os
import json
from runtime.rag_delivery.evidence_gate import enforce, EvidenceGateError

def test_evidence_gate_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert enforce({"evidence_status": "ok"}) is True
    with __import__('pytest').raises(EvidenceGateError):
        enforce({"evidence_status": "conflict", "failure_type": "EVIDENCE_CONFLICT"})

