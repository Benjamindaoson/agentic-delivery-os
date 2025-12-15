import os
import json
from runtime.contracts.worker_capability_manifest import generate_manifest

def test_worker_capability_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manifest = generate_manifest()
    out = os.path.join("artifacts", "contracts", "worker_capability_manifest.json")
    assert os.path.exists(out)
    with open(out, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "workers" in data
