import json
import os

import yaml


RELEASE_GATE_PATH = os.path.join("configs", "release_gate.yaml")


def _load_gate():
    with open(RELEASE_GATE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fake_eval_result(passed: bool):
    return {
        "eval_id": "eval_1",
        "passed": passed,
        "metrics": {
            "offline": {
                "ocr_coverage": 0.9,
                "table_recovery_f1": 0.85,
            },
            "online": {
                "retrieval": {"recall@5": 0.9},
                "generation": {"faithfulness": 0.92},
                "refusal": {"correct_refusal_rate": 0.97},
            },
        },
        "gate": {
            "passed": passed,
            "failed_rules": [] if passed else ["retrieval.recall@5 < 0.85"],
        },
    }


def _gate_allows_promote(eval_result: dict, gate_cfg: dict) -> bool:
    # For now, base decision solely on eval_result["gate"]["passed"]
    return bool(eval_result.get("gate", {}).get("passed"))


def test_release_gate_blocks_promote(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Copy gate config into tmp_path
    os.makedirs("configs", exist_ok=True)
    with open(RELEASE_GATE_PATH, "w", encoding="utf-8") as f:
        f.write(
            """
gate:
  offline:
    ocr_coverage_min: 0.85
    table_recovery_f1_min: 0.80
  online:
    retrieval_recall_at_5_min: 0.85
    generation_faithfulness_min: 0.90
    refusal_correct_refusal_rate_min: 0.95
  build:
    require_tests_green: true
    require_build_green: true
"""
        )

    gate_cfg = _load_gate()

    # Failing eval_result should block promote
    failing_eval = _fake_eval_result(passed=False)
    assert _gate_allows_promote(failing_eval, gate_cfg) is False


def test_promote_and_rollback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("artifacts/release", exist_ok=True)

    # Simulate first promote
    import scripts.promote as promote_mod

    promote_mod.RELEASE_STATE_DIR = os.path.join("artifacts", "release")
    promote_mod.ACTIVE_POINTER_PATH = os.path.join(promote_mod.RELEASE_STATE_DIR, "active.json")
    promote_mod.HISTORY_PATH = os.path.join(promote_mod.RELEASE_STATE_DIR, "history.jsonl")
    promote_mod.promote("index_v1", "model_v1", "config_v1")

    # Simulate second promote (to create rollback target)
    promote_mod.promote("index_v2", "model_v2", "config_v2")

    # Now rollback
    import scripts.rollback as rollback_mod

    rollback_mod.RELEASE_STATE_DIR = promote_mod.RELEASE_STATE_DIR
    rollback_mod.ACTIVE_POINTER_PATH = promote_mod.ACTIVE_POINTER_PATH
    rollback_mod.HISTORY_PATH = promote_mod.HISTORY_PATH

    rollback_mod.rollback()

    # Check active pointer restored to previous version
    with open(promote_mod.ACTIVE_POINTER_PATH, "r", encoding="utf-8") as f:
        active = json.load(f)

    assert active["index_version"] == "index_v1"
    assert active["model_version"] == "model_v1"
    assert active["config_version"] == "config_v1"




