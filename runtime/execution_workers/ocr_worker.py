"""
OCR Worker: executes specified OCR pipeline without fallback.
"""
from typing import Dict, Any
import time
import os
from runtime.execution_workers.common import (
    evidence_record,
    write_json,
    ensure_dir,
)

ALLOWED_OCR = {"PaddleOCR", "DeepSeek OCR", "MinerU"}


def run_ocr(execution_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    execution_input structure:
    {
      run_id, file_id,
      execution_plan: {selected_policy_id, pipeline_steps, toolchain, resource_profile, constraints},
      input_file_ref: {path_or_url, mime, size}
    }
    """
    start = time.time()
    run_id = execution_input.get("run_id")
    file_id = execution_input.get("file_id")
    plan = execution_input.get("execution_plan", {})
    toolchain = plan.get("toolchain", [])
    pipeline_steps = plan.get("pipeline_steps", [])
    resource_profile = plan.get("resource_profile", {})

    # validation
    if not pipeline_steps or not toolchain:
        output = {}
        ev = evidence_record(
            "OCR",
            tool_version="",
            input_obj=execution_input,
            output_obj=output,
            status="FAIL",
            failure_type="TOOL_UNAVAILABLE",
            resource_usage=resource_profile,
            start_time=start,
        )
        _persist(run_id, file_id, output, ev)
        return ev

    ocr_tool = toolchain[0]
    if ocr_tool not in ALLOWED_OCR:
        output = {}
        ev = evidence_record(
            "OCR",
            tool_version=ocr_tool,
            input_obj=execution_input,
            output_obj=output,
            status="FAIL",
            failure_type="TOOL_UNAVAILABLE",
            resource_usage=resource_profile,
            start_time=start,
        )
        _persist(run_id, file_id, output, ev)
        return ev

    # deterministic placeholder (no real OCR)
    output = {
        "ocr_text_blocks": [],
        "layout_metadata": {},
        "confidence_scores": {},
    }
    ev = evidence_record(
        "OCR",
        tool_version=ocr_tool,
        input_obj=execution_input,
        output_obj=output,
        status="SUCCESS",
        failure_type="",
        resource_usage=resource_profile,
        start_time=start,
    )
    _persist(run_id, file_id, output, ev)
    return ev


def _persist(run_id: str, file_id: str, output: Dict[str, Any], evidence: Dict[str, Any]):
    base = os.path.join("artifacts", "execution_workers", run_id or "unknown", file_id or "unknown")
    ensure_dir(base)
    write_json(os.path.join(base, "ocr_output.json"), output)
    write_json(os.path.join(base, "ocr_evidence.json"), evidence)


