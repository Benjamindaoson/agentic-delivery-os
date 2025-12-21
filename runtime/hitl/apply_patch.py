import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from backend.offline.dq_engine import build_dq_report, compute_metrics, decide_dq
from .offline_hitl import HITL_QUEUE_DIR


ARTIFACTS_OFFLINE_DIR = os.path.join("artifacts", "offline")


class HitlPatchError(Exception):
    pass


def _load_hitl_task(job_id: str) -> Dict[str, Any]:
    path = os.path.join(HITL_QUEUE_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        raise HitlPatchError(f"HITL task not found for job_id={job_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_parsed_doc(job_id: str) -> Dict[str, Any]:
    # For Offline Pipeline we expect ParsedDoc at artifacts/offline/{job_id}/parsed_doc.json
    base = os.path.join(ARTIFACTS_OFFLINE_DIR, job_id)
    path = os.path.join(base, "parsed_doc.json")
    if not os.path.exists(path):
        raise HitlPatchError(f"ParsedDoc not found for job_id={job_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _persist_parsed_doc(job_id: str, parsed_doc: Dict[str, Any]) -> str:
    base = os.path.join(ARTIFACTS_OFFLINE_DIR, job_id)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, "parsed_doc.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(parsed_doc, f, indent=2, ensure_ascii=False)
    return path


def _partial_update_parsed_doc(parsed_doc: Dict[str, Any], patch: Dict[str, Any]) -> None:
    """
    Apply a minimal, local mutation to ParsedDoc based on patch_type.

    Patch invariants:
    - Never modify original binary document
    - Only touch ParsedDoc/table grid/chunk metadata
    """
    patch_type = patch.get("patch_type")
    target = patch.get("target") or {}
    page_index = max(int(target.get("page", 1)) - 1, 0)

    before = patch.get("before")
    after = patch.get("after")

    pages = parsed_doc.setdefault("pages", [])
    while len(pages) <= page_index:
        pages.append({"page_number": len(pages) + 1, "text": "", "tables": []})
    page = pages[page_index]

    if patch_type in ("ocr_cell", "table_cell"):
        tables = page.setdefault("tables", [])
        if not tables:
            tables.append({"cells": [[before]]})
        table = tables[0]
        cells = table.setdefault("cells", [[before]])
        if cells and cells[0] and cells[0][0] == before:
            cells[0][0] = after
        # Mark OCR coverage as improved in a local, deterministic way
        ocr = parsed_doc.setdefault("ocr_output", {})
        blocks = ocr.setdefault("ocr_text_blocks", [])
        if not blocks:
            blocks.append({"text": after})

    elif patch_type == "table_header":
        tables = page.setdefault("tables", [])
        if not tables:
            tables.append({"header": before})
        header_table = tables[0]
        header_table["header"] = after

    elif patch_type == "chunk_boundary":
        chunks = parsed_doc.setdefault("chunks", [])
        if not chunks:
            chunks.append({"id": "chunk-1", "text": before})
        # Only touch first chunk for minimal adjustment
        if chunks[0].get("text") == before:
            chunks[0]["text"] = after

    else:
        raise HitlPatchError(f"Unsupported patch_type: {patch_type}")


def apply_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a HITL patch and perform partial rebuild:

    - Validate against existing HITL task and allowed_patch_types
    - Apply minimal mutation to ParsedDoc
    - Re-run DQ gate
    - If DQ == PASS → mark ready_to_continue = True
      If DQ == WARN → keep in HITL
      If DQ == FAIL → mark terminal failure

    Returns a summary dict for auditing.
    """
    job_id = patch.get("job_id")
    if not job_id:
        raise HitlPatchError("job_id is required")

    task = _load_hitl_task(job_id)
    if patch.get("patch_type") not in (task.get("allowed_patch_types") or []):
        raise HitlPatchError("patch_type not allowed for this HITL task")

    # Apply minimal patch to ParsedDoc
    parsed_doc = _load_parsed_doc(job_id)
    _partial_update_parsed_doc(parsed_doc, patch)
    _persist_parsed_doc(job_id, parsed_doc)

    # Re-run DQ on updated ParsedDoc
    metrics = compute_metrics(parsed_doc)
    decision = decide_dq(metrics)
    report = build_dq_report(parsed_doc, doc_id=job_id, run_id=job_id)
    # Persist updated DQ report alongside ParsedDoc
    dq_path = os.path.join(ARTIFACTS_OFFLINE_DIR, job_id, "dq_report.json")
    with open(dq_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Derive pipeline continuation flags
    if decision.level == "PASS":
        status = "ready_to_continue"
    elif decision.level == "WARN":
        status = "still_in_hitl"
    else:
        status = "failed"

    return {
        "job_id": job_id,
        "status": status,
        "dq_level": decision.level,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

























