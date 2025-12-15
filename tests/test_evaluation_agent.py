from runtime.evaluation.evaluation_agent import evaluate

def test_evaluation_agent_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {
        "answer_chunks": ["c1"],
        "allowed_sources": ["s1"],
        "evidence_map": {"c1": {"source_id": "s1", "source_type": "internal"}},
        "policy_constraints": []
    }
    res = evaluate(payload)
    assert res["pass"] is True


def test_evaluation_agent_fail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {
        "answer_chunks": ["c1"],
        "allowed_sources": ["s1"],
        "evidence_map": {"c1": {"source_id": "s2", "source_type": "external"}},
        "policy_constraints": ["NO_EXTERNAL"]
    }
    res = evaluate(payload)
    assert res["pass"] is False
    assert "POLICY_VIOLATION" in res["failed_checks"]
