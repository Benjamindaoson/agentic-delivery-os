import os
import json
from runtime.governance.failure_aggregator import failure_aggregator_singleton


def test_failure_aggregation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    failure_aggregator_singleton.base_dir = "artifacts/governance"
    os.makedirs(failure_aggregator_singleton.base_dir, exist_ok=True)
    failure_aggregator_singleton.record("runX", {
        "failed_nodes": ["N1"],
        "failure_type": "FT",
        "execution_path": "FULL",
        "failed_agent": "A1",
        "input_profile": {"size": 1}
    })
    result = failure_aggregator_singleton.aggregate()
    assert "failure_pattern" in result
    assert os.path.exists(os.path.join("artifacts", "governance", "failure_pattern.json"))
