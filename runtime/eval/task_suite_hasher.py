"""
Task Suite Hasher: 计算 task_suite.json 的 hash
"""
import json
import hashlib
import os

def calculate_task_suite_hash():
    """计算 task_suite.json 的 hash"""
    suite_path = "runtime/eval/task_suite.json"
    
    with open(suite_path, "r", encoding="utf-8") as f:
        suite_data = json.load(f)
    
    # 更新每个任务的 fixed_input_hash
    for task in suite_data.get("tasks", []):
        input_spec = task.get("fixed_input_spec", {})
        input_json = json.dumps(input_spec, sort_keys=True)
        input_hash = hashlib.sha256(input_json.encode()).hexdigest()
        task["fixed_input_hash"] = f"sha256:{input_hash}"
    
    # 保存更新后的 suite
    with open(suite_path, "w", encoding="utf-8") as f:
        json.dump(suite_data, f, indent=2, ensure_ascii=False)
    
    # 计算 suite hash
    suite_json = json.dumps(suite_data, sort_keys=True)
    suite_hash = hashlib.sha256(suite_json.encode()).hexdigest()
    
    # 保存 hash
    hash_path = "runtime/eval/task_suite.hash"
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(f"sha256:{suite_hash}")
    
    print(f"Task suite hash: sha256:{suite_hash}")
    return suite_hash

if __name__ == "__main__":
    calculate_task_suite_hash()


