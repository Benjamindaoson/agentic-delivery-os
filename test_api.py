"""
测试脚本：验证系统可稳定运行
连续执行 2 次完整任务，验证 task_id 不冲突，artifacts 不覆盖
"""
import requests
import json
import time
import os

BASE_URL = "http://localhost:8000/api"

def test_single_task():
    """测试单次任务执行"""
    print("=" * 60)
    print("Testing single task execution...")
    print("=" * 60)
    
    # 1. 提交空 Spec
    spec = {}
    response = requests.post(f"{BASE_URL}/delivery/submit", json=spec)
    assert response.status_code == 200, f"Submit failed: {response.status_code}"
    result = response.json()
    task_id = result["taskId"]
    print(f"✓ Task created: {task_id}")
    
    # 2. 轮询任务状态
    max_wait = 30
    wait_time = 0
    while wait_time < max_wait:
        response = requests.get(f"{BASE_URL}/task/{task_id}/status")
        assert response.status_code == 200, f"Status check failed: {response.status_code}"
        status = response.json()
        state = status["state"]
        print(f"  State: {state}")
        
        if state == "COMPLETED":
            print(f"✓ Task completed successfully!")
            break
        elif state == "FAILED":
            print(f"✗ Task failed: {status.get('error')}")
            break
        
        time.sleep(1)
        wait_time += 1
    
    # 3. 验证产物
    artifact_dir = os.path.join("artifacts", "rag_project", task_id)
    assert os.path.exists(artifact_dir), f"Artifact directory not found: {artifact_dir}"
    
    manifest_path = os.path.join(artifact_dir, "delivery_manifest.json")
    assert os.path.exists(manifest_path), f"Manifest not found: {manifest_path}"
    
    readme_path = os.path.join(artifact_dir, "README.md")
    assert os.path.exists(readme_path), f"README not found: {readme_path}"
    
    trace_path = os.path.join(artifact_dir, "system_trace.json")
    assert os.path.exists(trace_path), f"Trace not found: {trace_path}"
    
    # 验证 manifest 内容
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["task_id"] == task_id
        assert len(manifest["executed_agents"]) > 0
        print(f"✓ Artifacts generated correctly")
        print(f"  - Executed agents: {', '.join(manifest['executed_agents'])}")
    
    return task_id, state == "COMPLETED"

def test_multiple_tasks():
    """测试多次任务执行，验证不冲突"""
    print("\n" + "=" * 60)
    print("Testing multiple task execution...")
    print("=" * 60)
    
    task_ids = []
    for i in range(2):
        print(f"\n--- Task {i+1} ---")
        task_id, success = test_single_task()
        task_ids.append(task_id)
        
        if not success:
            print(f"✗ Task {i+1} failed")
            return False
        
        # 验证产物目录不冲突
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        assert os.path.exists(artifact_dir), f"Artifact directory not found for task {i+1}"
        print(f"✓ Task {i+1} artifacts in: {artifact_dir}")
    
    # 验证所有任务 ID 不同
    assert len(set(task_ids)) == len(task_ids), "Task IDs conflict!"
    print(f"\n✓ All {len(task_ids)} tasks completed with unique IDs")
    return True

if __name__ == "__main__":
    print("Agentic AI Delivery OS - API Test")
    print("=" * 60)
    
    # 检查后端是否运行
    try:
        response = requests.get(f"{BASE_URL.replace('/api', '')}/api/health")
        assert response.status_code == 200, "Backend not running!"
        print("✓ Backend is running")
    except Exception as e:
        print(f"✗ Backend not accessible: {e}")
        print("Please start the backend first: python backend/main.py")
        exit(1)
    
    # 运行测试
    try:
        success = test_multiple_tasks()
        if success:
            print("\n" + "=" * 60)
            print("✓ All tests passed!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("✗ Some tests failed")
            print("=" * 60)
            exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)




