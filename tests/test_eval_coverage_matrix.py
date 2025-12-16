import json
import os

from backend.eval.coverage_matrix import build_coverage_matrix
from backend.eval.eval_runner import write_eval_report


def test_eval_coverage_matrix_pass():
    eval_report = {
        "metrics": {
            "offline": {
                "parse": {"ocr": 0.9},
                "chunk": {"stability": 0.95},
            },
            "online": {
                "retrieval": {"recall@k": 0.9},
                "verification": {"coverage": 0.8},
            },
            "hitl": {"fix_rate": 0.5},
            "cost": {"budget": 10.0},
        }
    }
    matrix = build_coverage_matrix(eval_report)
    assert matrix["offline.parse.ocr"]["covered"] is True
    assert matrix["offline.chunk.stability"]["covered"] is True
    assert matrix["online.retrieval.recall@k"]["covered"] is True
    assert matrix["online.verification.coverage"]["covered"] is True
    assert matrix["hitl.fix_rate"]["covered"] is True
    assert matrix["cost.budget"]["covered"] is True


def test_eval_coverage_matrix_missing_metrics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    eval_report = {
        "metrics": {
            "offline": {
                "parse": {"ocr": 0.9},
            },
            "online": {
                "retrieval": {},
            },
        }
    }
    matrix = build_coverage_matrix(eval_report)
    # offline.parse.ocr present
    assert matrix["offline.parse.ocr"]["covered"] is True
    # others missing
    assert matrix["offline.chunk.stability"]["covered"] is False
    assert matrix["online.retrieval.recall@k"]["covered"] is False
    assert matrix["online.rerank"]["covered"] is False
    assert matrix["online.verification.coverage"]["covered"] is False
    assert matrix["hitl.fix_rate"]["covered"] is False
    assert matrix["latency.slo"]["covered"] is False

    # Ensure eval_runner attaches coverage_matrix to persisted report
    out_path = write_eval_report(eval_report, os.path.join("artifacts", "eval_report.json"))
    assert os.path.exists(out_path)
    with open(out_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert "coverage_matrix" in loaded
    assert loaded["coverage_matrix"]["offline.parse.ocr"]["covered"] is True




