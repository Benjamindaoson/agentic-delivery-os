import json
import os
import tempfile

from runtime.replay.replay_runner import replay_task


def make_sample_artifact(tmp_dir):
    task_dir = os.path.join(tmp_dir, "task-1")
    os.makedirs(task_dir, exist_ok=True)
    # simple trace with two agent executions
    trace = {
        "task_id": "task-1",
        "agent_executions": [
            {
                "agent": "Product",
                "output": {"decision": "proceed", "reason": "ok"},
                "llm_info": {"provider": "mock", "model_name": "mock-model", "prompt_hash": "abc"},
                "tool_executions": []
            },
            {
                "agent": "Execution",
                "output": {"decision": "execution_complete", "reason": "built"},
                "llm_info": None,
                "tool_executions": [
                    {"tool_name": "command_execute", "exit_code": 0}
                ]
            }
        ],
        "execution_plan": {"plan_id": "normal_v1"}
    }
    with open(os.path.join(task_dir, "system_trace.json"), "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    manifest = {
        "task_id": "task-1",
        "executed_agents": ["Product", "Execution"]
    }
    with open(os.path.join(task_dir, "delivery_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return task_dir


def test_replay_consistent(tmp_path):
    task_dir = make_sample_artifact(str(tmp_path))
    # place artifact under repository artifacts/rag_project/<task_id>
    dest_root = os.path.join(os.getcwd(), "artifacts", "rag_project")
    os.makedirs(dest_root, exist_ok=True)
    import shutil
    shutil.copytree(task_dir, os.path.join(dest_root, "task-1"), dirs_exist_ok=True)

    # run replay
    report = replay_task("task-1")
    assert report["consistent"] is True
    assert report["num_diffs"] == 0


