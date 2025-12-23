import json
import os

from backend.eval.coverage_matrix import build_coverage_matrix
from backend.eval.eval_signal_generator import (
    generate_eval_signals,
    EVAL_SIGNAL_PATH,
)


def test_eval_signal_generated_for_abnormal_metrics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    eval_report = {
        "metrics": {
            "online": {
                "numeric": {"numeric_mismatch_rate": 0.25, "numeric_mismatch_threshold": 0.1},
                "retrieval": {"recall@5": 0.7},
            },
            "hitl": {"fix_rate": 0.05, "fix_rate_threshold": 0.2},
        }
    }
    coverage = build_coverage_matrix(eval_report)
    result = generate_eval_signals(eval_report, coverage)

    assert os.path.exists(EVAL_SIGNAL_PATH)
    signals = result["signals"]
    types = {s["type"] for s in signals}
    assert "numeric_mismatch_rate_high" in types
    assert "retrieval_recall_low" in types
    assert "hitl_fix_rate_low" in types

    with open(EVAL_SIGNAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["signals"]) == len(signals)


def test_eval_signal_not_generated_when_metrics_normal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    eval_report = {
        "metrics": {
            "online": {
                "numeric": {"numeric_mismatch_rate": 0.05, "numeric_mismatch_threshold": 0.1},
                "retrieval": {"recall@5": 0.9},
            },
            "hitl": {"fix_rate": 0.3, "fix_rate_threshold": 0.2},
        }
    }
    coverage = build_coverage_matrix(eval_report)
    result = generate_eval_signals(eval_report, coverage)

    # No signals expected when everything is within thresholds
    assert result["signals"] == []






























