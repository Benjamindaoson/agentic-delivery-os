import os
from runtime.rag_delivery.worker import build_delivery


def test_rag_delivery_worker_smoke(tmp_path, monkeypatch):
    base = tmp_path / "artifacts"
    monkeypatch.chdir(tmp_path)
    payload = {
        "delivery_spec": {"audience": "test"},
        "data_manifest": {"files": [{"file_id": "f1"}]},
        "chunking_strategy": {"version": "v1"},
        "retrieval_config": {"topk": 3},
        "model_routing_config": {"embedding": "mock"},
    }
    res = build_delivery("run_smoke", payload)
    assert os.path.exists("artifacts/rag_delivery/run_smoke/delivery_bundle.json")
    assert "delivery_bundle_hash" in res["hashes"]


