import os
import json
from runtime.delivery.deploy_adapter import deploy
from runtime.delivery.rollback_adapter import rollback

def test_deploy_rollback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bundle = {
        "corpus_path": "c",
        "index_path": "i",
        "retrieval_config": {},
        "model_routing_config": {},
        "delivery_bundle_hash": ""
    }
    bundle["delivery_bundle_hash"] = __import__("hashlib").sha256(__import__("json").dumps({k:v for k,v in bundle.items() if k!="delivery_bundle_hash"}, sort_keys=True).encode()).hexdigest()
    path = os.path.join("bundle.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f)
    cfg = deploy(path)
    assert os.path.exists(os.path.join("artifacts", "deployments", "active_runtime.json"))
    res = rollback(path)
    assert res["status"] == "restored"
