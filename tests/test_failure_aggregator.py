import json
import os
from runtime.governance.failure_aggregator import failure_aggregator_singleton


def test_failure_aggregator(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    failure_aggregator_singleton.base_dir = "artifacts/failures"
    os.makedirs(failure_aggregator_singleton.base_dir, exist_ok=True)
    failure_aggregator_singleton.record("run1", {"failed_nodes": ["A"], "failure_type": "X"})
    result = failure_aggregator_singleton.aggregate()
    assert "failure_pattern" in result


