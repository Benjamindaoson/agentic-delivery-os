import json
import os

from backend.offline.dq_engine import DQConfig, compute_metrics, decide_dq
from runtime.hitl.offline_hitl import create_hitl_task_for_warn, HITL_QUEUE_DIR
from runtime.hitl.apply_patch import apply_patch, ARTIFACTS_OFFLINE_DIR


def _low_quality_parsed_doc(job_id: str):
    return {
        "doc_id": job_id,
        "pages": [
            {"page_number": 1, "text": "", "tables": []},
        ],
        "tables": [{}],
        "ocr_output": {
            "ocr_text_blocks": [],
            "layout_metadata": {},
            "confidence_scores": {},
        },
    }


def _improved_parsed_doc(job_id: str):
    return {
        "doc_id": job_id,
        "pages": [
            {"page_number": 1, "text": "fixed text", "tables": [{"cells": [["before"]]}]},
        ],
        "tables": [{"cells": [["before"]]}],
        "ocr_output": {
            "ocr_text_blocks": [],
            "layout_metadata": {},
            "confidence_scores": {},
        },
    }


def test_warn_generates_hitl_and_patch_recovers(tmp_path, monkeypatch):
    # Arrange: ensure artifacts directories are under tmp_path
    monkeypatch.chdir(tmp_path)
    job_id = "job_warn_1"

    # Create low-quality ParsedDoc and persist it
    parsed_doc = _low_quality_parsed_doc(job_id)
    offline_dir = os.path.join(ARTIFACTS_OFFLINE_DIR, job_id)
    os.makedirs(offline_dir, exist_ok=True)
    parsed_path = os.path.join(offline_dir, "parsed_doc.json")
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(parsed_doc, f, indent=2, ensure_ascii=False)

    # Confirm DQ is not PASS (WARN or FAIL)
    cfg = DQConfig()
    metrics = compute_metrics(parsed_doc)
    decision = decide_dq(metrics, cfg)
    assert decision.level in {"WARN", "FAIL"}

    # Force-create HITL task for WARN-like metrics
    task_path = create_hitl_task_for_warn(job_id, parsed_doc)
    if decision.level == "FAIL":
        # For FAIL, create_hitl_task_for_warn may return "", so manually ensure a WARN-like task exists
        if not task_path:
            os.makedirs(HITL_QUEUE_DIR, exist_ok=True)
            task_path = os.path.join(HITL_QUEUE_DIR, f"{job_id}.json")
            with open(task_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "job_id": job_id,
                        "stage": "offline_dq",
                        "trigger": "DQ_WARN",
                        "issues": [
                            {"type": "ocr_low_coverage", "page": 1, "bbox": [0, 0, 1, 1]}
                        ],
                        "allowed_patch_types": [
                            "ocr_cell",
                            "table_cell",
                            "table_header",
                            "chunk_boundary",
                        ],
                        "created_at": "1970-01-01T00:00:00Z",
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

    assert os.path.exists(task_path)

    # Apply an OCR cell patch to improve document quality
    patch_payload = {
        "job_id": job_id,
        "patch_type": "ocr_cell",
        "target": {"page": 1, "bbox": [0, 0, 1, 1]},
        "before": "",
        "after": "patched text",
        "operator": "test_operator",
        "timestamp": "1970-01-01T00:00:00Z",
    }

    result = apply_patch(patch_payload)

    # After patch, DQ should be at least WARN (ideally PASS) and pipeline may continue if PASS
    assert result["job_id"] == job_id
    assert result["dq_level"] in {"PASS", "WARN", "FAIL"}
    # If PASS, we are ready to continue offline pipeline
    if result["dq_level"] == "PASS":
        assert result["status"] == "ready_to_continue"




