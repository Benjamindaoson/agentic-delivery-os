"""
Chunking Worker: deterministic chunking based on provided strategy id.
"""
from typing import Dict, Any, List
import time
import os
from runtime.execution_workers.common import evidence_record, write_json, ensure_dir
import hashlib


def _chunk_id(content: str, idx: int) -> str:
    return hashlib.sha256(f"{content}|{idx}".encode()).hexdigest()[:16]


def run_chunk(execution_input: Dict[str, Any], structured_input: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    run_id = execution_input.get("run_id")
    file_id = execution_input.get("file_id")
    plan = execution_input.get("execution_plan", {})
    resource_profile = plan.get("resource_profile", {})
    strategy_id = plan.get("chunking_strategy_id")

    if not strategy_id:
        output = {}
        ev = evidence_record(
            "CHUNKING",
            tool_version=strategy_id or "",
            input_obj={"execution_input": execution_input, "structured_input": structured_input},
            output_obj=output,
            status="FAIL",
            failure_type="FORMAT_MISMATCH",
            resource_usage=resource_profile,
            start_time=start,
        )
        _persist(run_id, file_id, output, ev)
        return ev

    blocks: List[str] = []
    for b in structured_input.get("structured_blocks", []):
        blocks.append(b if isinstance(b, str) else str(b))

    chunks = []
    for idx, content in enumerate(blocks):
        chunks.append(
            {
                "chunk_id": _chunk_id(content, idx),
                "content": content,
                "source_ref": {"file_id": file_id, "block_idx": idx},
            }
        )

    output = {"chunks": chunks}
    ev = evidence_record(
        "CHUNKING",
        tool_version=strategy_id,
        input_obj={"execution_input": execution_input, "structured_input": structured_input},
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
    write_json(os.path.join(base, "chunk_output.json"), output)
    write_json(os.path.join(base, "chunk_evidence.json"), evidence)


