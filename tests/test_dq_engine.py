import json
import os

from backend.offline.dq_engine import (
    compute_metrics,
    decide_dq,
    build_dq_report,
    persist_dq_report,
    DQConfig,
)


def _sample_parsed_doc_pass():
    return {
        "doc_id": "doc_pass",
        "pages": [
            {"page_number": 1, "text": "This is page one with some English text.", "tables": []},
            {"page_number": 2, "text": "第二页包含中文内容。", "tables": [{"cells": [[1, 2], [3, 4]]}]},
        ],
        "tables": [{"cells": [[1, 2]]}],
        "ocr_output": {
            "ocr_text_blocks": [{"text": "dummy"}],
            "layout_metadata": {},
            "confidence_scores": {},
        },
    }


def _sample_parsed_doc_fail():
    # Many empty / duplicate pages, no OCR, no tables recovered
    return {
        "doc_id": "doc_fail",
        "pages": [
            {"page_number": 1, "text": "", "tables": []},
            {"page_number": 2, "text": "", "tables": []},
            {"page_number": 3, "text": "", "tables": []},
            {"page_number": 4, "text": "", "tables": []},
        ],
        "tables": [{}],
        "ocr_output": {
            "ocr_text_blocks": [],
            "layout_metadata": {},
            "confidence_scores": {},
        },
    }


def test_dq_engine_pass(tmp_path):
    parsed = _sample_parsed_doc_pass()
    cfg = DQConfig(
        ocr_coverage_warn=0.6,
        ocr_coverage_fail=0.3,
        table_recovery_warn=0.5,
        table_recovery_fail=0.2,
        empty_page_ratio_warn=0.5,
        empty_page_ratio_fail=0.8,
        duplicate_page_ratio_warn=0.5,
        duplicate_page_ratio_fail=0.8,
    )
    metrics = compute_metrics(parsed)
    decision = decide_dq(metrics, cfg)
    assert decision.level == "PASS"

    report = build_dq_report(parsed, config_path=None, doc_id="doc_pass", run_id="run1")
    path = persist_dq_report(report, base_dir=str(tmp_path))
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["decision"]["level"] == "PASS"
    assert loaded["metrics"]["language"] in {"en", "zh", "mixed", "unknown"}


def test_dq_engine_fail(tmp_path):
    parsed = _sample_parsed_doc_fail()
    cfg = DQConfig(
        ocr_coverage_warn=0.6,
        ocr_coverage_fail=0.3,
        table_recovery_warn=0.7,
        table_recovery_fail=0.4,
        empty_page_ratio_warn=0.5,
        empty_page_ratio_fail=0.8,
        duplicate_page_ratio_warn=0.3,
        duplicate_page_ratio_fail=0.6,
    )
    metrics = compute_metrics(parsed)
    decision = decide_dq(metrics, cfg)
    assert decision.level == "FAIL"
    assert any("ocr_coverage" in r or "empty_page_ratio" in r for r in decision.reasons)

    report = build_dq_report(parsed, config_path=None, doc_id="doc_fail", run_id="run2")
    path = persist_dq_report(report, base_dir=str(tmp_path))
    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["decision"]["level"] in {"WARN", "FAIL"}































