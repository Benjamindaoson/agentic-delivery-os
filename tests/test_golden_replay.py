import os
import shutil
from runtime.replay.replay_runner import replay_task


def test_golden_replay(tmp_path):
    # copy checked-in golden artifact into repository artifacts/rag_project/task-golden
    src = os.path.join("tests", "golden", "task_golden")
    dest_root = os.path.join(os.getcwd(), "artifacts", "rag_project")
    os.makedirs(dest_root, exist_ok=True)
    shutil.copytree(src, os.path.join(dest_root, "task-golden"), dirs_exist_ok=True)

    # run replay (the function reads artifacts/rag_project/task-golden)
    report = replay_task("task-golden")
    assert report["consistent"] is True
    assert report["num_diffs"] == 0


