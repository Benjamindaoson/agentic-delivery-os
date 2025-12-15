import json
import os
from runtime.rag_delivery.execution_paths import record_path, PATHS


def test_record_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = record_path("run1", "FULL_RAG_PATH", "default")
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["path_id"] in PATHS


