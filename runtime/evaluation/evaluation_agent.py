"""
Evaluation Agent: evidence coverage, citation consistency, policy/permission checks.
Structured output only.
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime


def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload fields expected:
    - answer_chunks: list of chunk_ids referenced
    - allowed_sources: list of source ids
    - evidence_map: mapping chunk_id -> source_id/content
    - policy_constraints: list of forbidden sources or rules
    """
    answer_chunks: List[str] = payload.get("answer_chunks", [])
    evidence_map = payload.get("evidence_map", {})
    allowed_sources = set(payload.get("allowed_sources", []))
    policy_constraints = payload.get("policy_constraints", [])

    failed = []
    severity = "BLOCK"

    # Evidence coverage
    if not answer_chunks:
        failed.append("EVIDENCE_INSUFFICIENT")

    # Citation consistency
    for cid in answer_chunks:
        if cid not in evidence_map:
            failed.append("CITATION_INCONSISTENT")
            break

    # Policy / permission
    for cid in answer_chunks:
        src = evidence_map.get(cid, {}).get("source_id")
        if allowed_sources and src not in allowed_sources:
            failed.append("POLICY_VIOLATION")
            break
    for rule in policy_constraints:
        if rule == "NO_EXTERNAL" and any(evidence_map.get(c, {}).get("source_type") == "external" for c in answer_chunks):
            failed.append("POLICY_VIOLATION")
            break

    passed = len(failed) == 0
    result = {
        "pass": passed,
        "failed_checks": failed,
        "failed_agent_id": payload.get("agent_id", ""),
        "failed_node_id": payload.get("node_id", ""),
        "severity": severity if not passed else "NONE",
        "replay_pointer": payload.get("replay_pointer", ""),
        "timestamp": datetime.now().isoformat(),
    }

    out_dir = os.path.join("artifacts", "evaluation")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "evaluation_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


