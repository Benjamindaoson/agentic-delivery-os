"""
Document Parsing Worker: deterministic parser selection.
"""
from typing import Dict, Any
import time
import os
from runtime.execution_workers.common import evidence_record, write_json, ensure_dir

PARSER_BINDINGS = {
    "application/pdf": "pdfplumber",
    "application/msword": "python-docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "python-docx",
    "text/html": "trafilatura",
    "application/vnd.ms-excel": "openpyxl",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "openpyxl",
    "text/csv": "openpyxl",
}


def run_parse(execution_input: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    run_id = execution_input.get("run_id")
    file_id = execution_input.get("file_id")
    plan = execution_input.get("execution_plan", {})
    resource_profile = plan.get("resource_profile", {})
    mime = execution_input.get("input_file_ref", {}).get("mime", "")

    parser = PARSER_BINDINGS.get(mime)
    pipeline_steps = plan.get("pipeline_steps", [])

    if not parser or not pipeline_steps:
        output = {}
        ev = evidence_record(
            "PARSING",
            tool_version=parser or "",
            input_obj=execution_input,
            output_obj=output,
            status="FAIL",
            failure_type="FORMAT_MISMATCH",
            resource_usage=resource_profile,
            start_time=start,
        )
        _persist(run_id, file_id, output, ev)
        return ev

    output = {
        "structured_blocks": [],
        "tables": [],
        "metadata": {"parser": parser},
    }
    ev = evidence_record(
        "PARSING",
        tool_version=parser,
        input_obj=execution_input,
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
    write_json(os.path.join(base, "parse_output.json"), output)
    write_json(os.path.join(base, "parse_evidence.json"), evidence)


