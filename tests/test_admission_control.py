import os
import json
from runtime.execution_control.admission import decide_admission

def test_admission_control(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task = {"task_id": "t1", "size": 10, "pages": 2, "rows": 0, "unattended": True}
    constraints = {"max_size": 20, "max_pages": 10, "max_rows": 100, "allow_unattended": True}
    result = decide_admission(task, constraints)
    assert result["decision"] == "ALLOW"
    assert os.path.exists(os.path.join("artifacts", "execution_control", "admission_decision.json"))
