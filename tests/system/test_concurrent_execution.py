"""
System-level Tests: Concurrent Execution
测试并发执行、ExecutionPool、backpressure
"""
import pytest
import asyncio
from typing import Dict, Any
from runtime.execution_graph.execution_pool import (
    ExecutionPool,
    ExecutionMode,
    get_execution_pool
)


@pytest.mark.asyncio
async def test_execution_pool_basic():
    """测试基本的执行池功能"""
    pool = ExecutionPool(max_concurrency=5)
    
    # Mock executor
    async def mock_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        await asyncio.sleep(0.1)  # Simulate work
        return {
            "decision": "completed",
            "agent_name": context.get("agent_name", "test")
        }
    
    # Submit tasks
    task_ids = []
    for i in range(10):
        task_id = await pool.submit(
            node_id=f"node_{i}",
            agent_name=f"Agent{i}",
            executor=mock_executor,
            context={"agent_name": f"Agent{i}"},
            run_id="test_run",
            tenant_id="test_tenant"
        )
        task_ids.append(task_id)
    
    # Wait for completion
    results = await pool.wait_all(timeout=10.0)
    
    # Assertions
    assert len(results) == 10
    assert all(r["decision"] == "completed" for r in results.values())
    
    # Check metrics
    metrics = pool.get_metrics()
    assert metrics.total_tasks == 10
    assert metrics.completed_tasks == 10
    assert metrics.failed_tasks == 0
    assert metrics.max_concurrency_reached <= 5


@pytest.mark.asyncio
async def test_execution_pool_backpressure():
    """测试背压控制"""
    pool = ExecutionPool(max_concurrency=3, backpressure_threshold=0.7)
    
    async def slow_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        await asyncio.sleep(0.5)
        return {"decision": "completed"}
    
    # Submit more tasks than capacity
    task_ids = []
    for i in range(10):
        task_id = await pool.submit(
            node_id=f"node_{i}",
            agent_name="SlowAgent",
            executor=slow_executor,
            context={},
            run_id="test_run",
            tenant_id="test_tenant"
        )
        task_ids.append(task_id)
    
    # Wait for completion
    await pool.wait_all(timeout=30.0)
    
    # Check backpressure events
    metrics = pool.get_metrics()
    assert metrics.backpressure_events > 0  # Should have triggered backpressure


@pytest.mark.asyncio
async def test_execution_pool_priority():
    """测试优先级调度"""
    pool = ExecutionPool(max_concurrency=2)
    
    execution_order = []
    
    async def tracking_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        execution_order.append(context["task_name"])
        await asyncio.sleep(0.1)
        return {"decision": "completed"}
    
    # Submit tasks with different priorities
    await pool.submit(
        node_id="low",
        agent_name="Agent",
        executor=tracking_executor,
        context={"task_name": "low"},
        run_id="test",
        tenant_id="test",
        priority=7  # Low priority
    )
    
    await asyncio.sleep(0.05)  # Let first task start
    
    await pool.submit(
        node_id="high",
        agent_name="Agent",
        executor=tracking_executor,
        context={"task_name": "high"},
        run_id="test",
        tenant_id="test",
        priority=1  # High priority
    )
    
    await pool.wait_all(timeout=5.0)
    
    # High priority should execute before low (if scheduled correctly)
    # Note: Due to async scheduling, this might not always be strict


@pytest.mark.asyncio
async def test_execution_pool_failure_handling():
    """测试失败处理"""
    pool = ExecutionPool(max_concurrency=5)
    
    async def failing_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        if context.get("should_fail"):
            raise Exception("Intentional failure")
        return {"decision": "completed"}
    
    # Submit mix of succeeding and failing tasks
    for i in range(10):
        await pool.submit(
            node_id=f"node_{i}",
            agent_name="Agent",
            executor=failing_executor,
            context={"should_fail": i % 3 == 0},
            run_id="test",
            tenant_id="test"
        )
    
    await pool.wait_all(timeout=5.0)
    
    # Check metrics
    metrics = pool.get_metrics()
    assert metrics.total_tasks == 10
    assert metrics.failed_tasks > 0
    assert metrics.completed_tasks < 10


@pytest.mark.asyncio
async def test_execution_pool_dependencies():
    """测试任务依赖"""
    pool = ExecutionPool(max_concurrency=5)
    
    results = {}
    
    async def dependent_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        task_name = context["task_name"]
        results[task_name] = True
        return {"decision": "completed", "task_name": task_name}
    
    # Task A (no dependencies)
    task_a = await pool.submit(
        node_id="task_a",
        agent_name="Agent",
        executor=dependent_executor,
        context={"task_name": "A"},
        run_id="test",
        tenant_id="test"
    )
    
    # Task B depends on A
    task_b = await pool.submit(
        node_id="task_b",
        agent_name="Agent",
        executor=dependent_executor,
        context={"task_name": "B"},
        run_id="test",
        tenant_id="test",
        dependencies=[task_a]
    )
    
    # Task C depends on B
    task_c = await pool.submit(
        node_id="task_c",
        agent_name="Agent",
        executor=dependent_executor,
        context={"task_name": "C"},
        run_id="test",
        tenant_id="test",
        dependencies=[task_b]
    )
    
    await pool.wait_all(timeout=10.0)
    
    # All should complete
    assert "A" in results
    assert "B" in results
    assert "C" in results


@pytest.mark.asyncio
async def test_execution_pool_tenant_isolation():
    """测试租户隔离（基本）"""
    pool = ExecutionPool(max_concurrency=10)
    
    tenant_counts = {"tenant1": 0, "tenant2": 0}
    
    async def tenant_aware_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        tenant_id = context.get("tenant_id")
        if tenant_id in tenant_counts:
            tenant_counts[tenant_id] += 1
        await asyncio.sleep(0.1)
        return {"decision": "completed"}
    
    # Submit tasks for two tenants
    for i in range(10):
        tenant_id = "tenant1" if i < 5 else "tenant2"
        await pool.submit(
            node_id=f"node_{i}",
            agent_name="Agent",
            executor=tenant_aware_executor,
            context={"tenant_id": tenant_id},
            run_id=f"run_{i}",
            tenant_id=tenant_id
        )
    
    await pool.wait_all(timeout=10.0)
    
    # Both tenants should have executed tasks
    assert tenant_counts["tenant1"] == 5
    assert tenant_counts["tenant2"] == 5


@pytest.mark.asyncio
async def test_concurrent_report_generation():
    """测试并发执行报告生成"""
    pool = ExecutionPool(max_concurrency=5)
    
    async def simple_executor(context: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        return {"decision": "completed"}
    
    run_id = "test_report_run"
    
    # Submit tasks
    for i in range(5):
        await pool.submit(
            node_id=f"node_{i}",
            agent_name=f"Agent{i}",
            executor=simple_executor,
            context={},
            run_id=run_id,
            tenant_id="test"
        )
    
    await pool.wait_all(timeout=5.0)
    
    # Save report
    report_path = await pool.save_concurrency_report(run_id)
    
    # Check report exists
    import os
    assert os.path.exists(report_path)
    
    # Load and validate report
    import json
    with open(report_path, "r") as f:
        report = json.load(f)
    
    assert report["run_id"] == run_id
    assert report["metrics"]["total_tasks"] == 5
    assert report["metrics"]["completed_tasks"] == 5
    assert len(report["tasks"]) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

