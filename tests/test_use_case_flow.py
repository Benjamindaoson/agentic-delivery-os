import json
from pathlib import Path
from shutil import copytree

from backend.eval.use_case_flow import EvalReport, GateDecision, LearningSignal, run_use_case_flow


def _prepare_use_cases(tmp_path, monkeypatch):
    src = Path("eval/use_cases")
    dst = Path(tmp_path) / "eval" / "use_cases"
    dst.parent.mkdir(parents=True, exist_ok=True)
    copytree(src, dst)
    monkeypatch.chdir(tmp_path)


def test_use_case_flow_promote(tmp_path, monkeypatch):
    _prepare_use_cases(tmp_path, monkeypatch)

    answer_bundle = {
        "annual_fee": {
            "fields": {"fee": 0.0, "condition": "刷卡3次免年费"},
            "citations": [{"chunk_id": "c1"}],
        },
        "cashback": {
            "fields": {"rate": 0.05, "category": "超市"},
            "citations": [{"chunk_id": "c2"}],
        },
        "terms_conflict": {
            "fields": {"conflict_detected": True},
            "citations": [{"chunk_id": "c3"}],
        },
    }

    eval_report, learning_signal, gate_decision = run_use_case_flow(answer_bundle, run_id="r1")

    assert isinstance(eval_report, EvalReport)
    assert isinstance(learning_signal, LearningSignal)
    assert isinstance(gate_decision, GateDecision)
    assert gate_decision.decision == "promote"
    assert learning_signal.signals == []

    base = Path("artifacts") / "runs" / "r1"
    assert (base / "eval_report.json").exists()
    assert (base / "learning_signal.jsonl").exists()
    assert (base / "gate_decision.json").exists()
    assert (base / "run_trace.json").exists()

    with open(base / "eval_report.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["status"] == "pass"


def test_use_case_flow_rollback_generates_learning(tmp_path, monkeypatch):
    _prepare_use_cases(tmp_path, monkeypatch)

    answer_bundle = {
        "annual_fee": {
            "fields": {"fee": 0.0},
            "citations": [{"chunk_id": "c1"}],
        }
    }

    eval_report, learning_signal, gate_decision = run_use_case_flow(answer_bundle, run_id="r2")

    assert gate_decision.decision == "rollback"
    assert eval_report.status == "fail"
    assert learning_signal.signals, "Learning signals must exist when eval fails"

    base = Path("artifacts") / "runs" / "r2"
    with open(base / "learning_signal.jsonl", "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert lines and lines[0]["signals"]
    assert lines[0]["eval_status"] == "fail"

    with open(base / "gate_decision.json", "r", encoding="utf-8") as f:
        gate_payload = json.load(f)
    assert gate_payload["decision"] == "rollback"


def test_use_case_flow_replay_consistent_decision(tmp_path, monkeypatch):
    _prepare_use_cases(tmp_path, monkeypatch)

    answers = {
        "annual_fee": {
            "fields": {"fee": 0.0, "condition": "刷卡3次免年费"},
            "citations": [{"chunk_id": "c1"}],
        },
        "cashback": {
            "fields": {"rate": 0.05, "category": "超市"},
            "citations": [{"chunk_id": "c2"}],
        },
        "terms_conflict": {
            "fields": {"conflict_detected": True},
            "citations": [{"chunk_id": "c3"}],
        },
    }

    _, _, gate_decision_first = run_use_case_flow(answers, run_id="replay")
    _, _, gate_decision_second = run_use_case_flow(answers, run_id="replay")

    assert gate_decision_first.decision == gate_decision_second.decision == "promote"

    base = Path("artifacts") / "runs" / "replay"
    with open(base / "gate_decision.json", "r", encoding="utf-8") as f:
        stored = json.load(f)
    assert stored["decision"] == "promote"
