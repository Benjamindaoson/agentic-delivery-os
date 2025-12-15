"""
测试脚本：验证 LLM 集成
- 连续执行 2 个任务
- 验证 LLM 成功和失败路径
- 打印 artifacts 和 trace 位置
"""
import requests
import json
import time
import os
import sys

BASE_URL = "http://localhost:8000/api"

def test_task_with_llm(llm_enabled: bool = True):
    """测试单次任务执行（LLM 启用/禁用）"""
    print("=" * 60)
    print(f"Testing task execution (LLM {'enabled' if llm_enabled else 'disabled'})...")
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
    
    trace_path = os.path.join(artifact_dir, "system_trace.json")
    assert os.path.exists(trace_path), f"Trace not found: {trace_path}"
    
    # 4. 检查 LLM 使用情况
    with open(trace_path, "r", encoding="utf-8") as f:
        trace = json.load(f)
    
    llm_used_count = 0
    llm_fallback_count = 0
    for agent_exec in trace.get("agent_executions", []):
        llm_info = agent_exec.get("llm_info")
        if llm_info:
            if llm_info.get("llm_used"):
                llm_used_count += 1
                print(f"  ✓ {agent_exec['agent']}: LLM used ({llm_info.get('provider')})")
            else:
                llm_fallback_count += 1
                print(f"  ⚠ {agent_exec['agent']}: LLM fallback ({llm_info.get('failure_code')})")
    
    print(f"\n  LLM Summary: {llm_used_count} used, {llm_fallback_count} fallback")
    
    return task_id, state == "COMPLETED", llm_used_count, llm_fallback_count

def test_multiple_tasks():
    """测试多次任务执行"""
    print("\n" + "=" * 60)
    print("Testing multiple task execution...")
    print("=" * 60)
    
    task_ids = []
    for i in range(2):
        print(f"\n--- Task {i+1} ---")
        task_id, success, llm_used, llm_fallback = test_task_with_llm()
        task_ids.append((task_id, success, llm_used, llm_fallback))
        
        if not success:
            print(f"✗ Task {i+1} failed")
            return False
        
        # 验证产物目录不冲突
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        assert os.path.exists(artifact_dir), f"Artifact directory not found for task {i+1}"
        print(f"✓ Task {i+1} artifacts in: {artifact_dir}")
    
    # 验证所有任务 ID 不同
    unique_ids = set(t[0] for t in task_ids)
    assert len(unique_ids) == len(task_ids), "Task IDs conflict!"
    
    print(f"\n✓ All {len(task_ids)} tasks completed with unique IDs")
    print(f"\nLLM Usage Summary:")
    for i, (task_id, success, llm_used, llm_fallback) in enumerate(task_ids, 1):
        print(f"  Task {i}: {llm_used} LLM calls succeeded, {llm_fallback} used fallback")
    
    return True

if __name__ == "__main__":
    print("Agentic AI Delivery OS - LLM Integration Test")
    print("=" * 60)
    
    # 检查后端是否运行
    try:
        response = requests.get(f"{BASE_URL.replace('/api', '')}/api/health")
        assert response.status_code == 200, "Backend not running!"
        print("✓ Backend is running")
    except Exception as e:
        print(f"✗ Backend not accessible: {e}")
        print("Please start the backend first: python backend/main.py")
        sys.exit(1)
    
    # 检查 LLM 配置
    llm_provider = os.getenv("LLM_PROVIDER", "qwen")
    qwen_key = os.getenv("QWEN_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    print(f"\nLLM Configuration:")
    print(f"  Provider: {llm_provider}")
    if llm_provider == "qwen":
        if qwen_key:
            print(f"  ✓ QWEN_API_KEY set")
        else:
            print(f"  ⚠ QWEN_API_KEY not set (will use fallback)")
    elif llm_provider == "openai":
        if openai_key:
            print(f"  ✓ OPENAI_API_KEY set")
        else:
            print(f"  ⚠ OPENAI_API_KEY not set (will use fallback)")
    
    # 运行测试
    try:
        success = test_multiple_tasks()
        if success:
            print("\n" + "=" * 60)
            print("✓ All tests passed!")
            print("=" * 60)
            print("\nArtifacts location: artifacts/rag_project/{task_id}/")
            print("Trace files: system_trace.json")
        else:
            print("\n" + "=" * 60)
            print("✗ Some tests failed")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


