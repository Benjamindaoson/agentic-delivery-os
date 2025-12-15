"""
Embedding Worker: deterministic embedding execution without fallback.
"""
from typing import Dict, Any, List
import time
import os
from runtime.execution_workers.common import evidence_record, write_json, ensure_dir, sha256_json


def run_embedding(execution_input: Dict[str, Any], chunks: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    run_id = execution_input.get("run_id")
    file_id = execution_input.get("file_id")
    plan = execution_input.get("execution_plan", {})
    resource_profile = plan.get("resource_profile", {})
    model_id = plan.get("embedding_model_id")

    if not model_id:
        output = {}
        ev = evidence_record(
            "EMBEDDING",
            tool_version=model_id or "",
            input_obj={"execution_input": execution_input, "chunks": chunks},
            output_obj=output,
            status="FAIL",
            failure_type="TOOL_UNAVAILABLE",
            resource_usage=resource_profile,
            start_time=start,
        )
        _persist(run_id, file_id, output, ev)
        return ev

    # Deterministic mock embeddings (hash-based)
    embeddings: List[str] = []
    for ch in chunks.get("chunks", []):
        embeddings.append(sha256_json(ch)[:32])

    output = {
        "embeddings": embeddings,
        "model_id": model_id,
        "cost_usage": {"tokens": len("".join(embeddings)), "usd": 0.0},
    }
    ev = evidence_record(
        "EMBEDDING",
        tool_version=model_id,
        input_obj={"execution_input": execution_input, "chunks": chunks},
        output_obj=output,
        status="SUCCESS",
        resource_usage=resource_profile,
        start_time=start,
    )
    _persist(run_id, file_id, output, ev)
    return ev


def _persist(run_id: str, file_id: str, output: Dict[str, Any], evidence: Dict[str, Any]):
    base = os.path.join("artifacts", "execution_workers", run_id or "unknown", file_id or "unknown")
    ensure_dir(base)
    write_json(os.path.join(base, "embedding_output.json"), output)
    write_json(os.path.join(base, "embedding_evidence.json"), evidence)


