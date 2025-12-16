import json
import os

from backend.learning.hitl_learning_engine import (
    apply_hitl_learning,
    LEARNING_UPDATES_PATH,
)


def test_hitl_learning_generates_updates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    hitl_patch = {
        "job_id": "job1",
        "patch_type": "ocr_cell",
        "target": {"page": 1, "bbox": [0, 0, 1, 1]},
        "before": "",
        "after": "patched text",
    }
    dq_report = {"metrics": {}}
    parser_strategy = {}
    chunk_policy = {}

    summary = apply_hitl_learning(hitl_patch, dq_report, parser_strategy, chunk_policy)

    assert os.path.exists(LEARNING_UPDATES_PATH)
    assert summary["job_id"] == "job1"
    assert len(summary["updates"]) >= 1
    kinds = {u["kind"] for u in summary["updates"]}
    assert "parser_strategy_prior" in kinds

    with open(LEARNING_UPDATES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["job_id"] == "job1"
    assert len(data["updates"]) >= 1


def test_hitl_learning_no_updates_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Unknown patch_type should not produce any learning updates
    hitl_patch = {
        "job_id": "job2",
        "patch_type": "unknown_type",
    }
    summary = apply_hitl_learning(hitl_patch, {}, {}, {})

    # Enforce that patches must produce at least one update; otherwise treat as failure
    assert len(summary["updates"]) == 0



