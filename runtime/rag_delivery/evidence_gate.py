"""
Evidence Gate: hard blocking before delivery worker.
"""
from typing import Dict, Any


class EvidenceGateError(Exception):
    pass


def enforce(evidence: Dict[str, Any]):
    """
    evidence must include:
    - evidence_status: "ok" | "insufficient" | "conflict" | "unauthorized"
    - failure_type if not ok
    """
    status = evidence.get("evidence_status", "insufficient")
    if status != "ok":
        failure_type = evidence.get("failure_type", "EVIDENCE_BLOCK")
        raise EvidenceGateError(failure_type)
    return True

