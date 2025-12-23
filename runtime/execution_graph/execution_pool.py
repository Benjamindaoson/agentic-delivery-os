"""
ExecutionPool: 并发执行池
支持 backpressure、max_concurrency、async execution
"""
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json
import os


class ExecutionMode(str, Enum):
    """节点执行模式"""
    SERIAL = "serial"  # 串行执行
    PARALLEL = "parallel"  # 并行执行
    MAP_REDUCE = "map_reduce"  # Map-Reduce 模式


@dataclass
class ExecutionTask:
    """执行任务"""
    task_id: str
    node_id: str
    agent_name: str
    context: Dict[str, Any]
    run_id: str
    tenant_id: str = "default"
    priority: int = 5  # 1-10, 1 highest
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status: str = "pending"  # pending/running/completed/failed


@dataclass
class PoolMetrics:
    """执行池指标"""
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    max_concurrency_reached: int = 0
    backpressure_events: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


class ExecutionPool:
    """
    并发执行池
    
    Features:
    - Async task execution with configurable max_concurrency
    - Backpressure control
    - Priority-based scheduling
    - Dependency resolution
    - Metrics collection
    """
    
    def __init__(
        self,
        max_concurrency: int = 10,
        backpressure_threshold: float = 0.8,  # 80% capacity triggers backpressure
        artifacts_dir: str = "artifacts/execution"
    ):
        self.max_concurrency = max_concurrency
        self.backpressure_threshold = backpressure_threshold
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Internal state
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._pending_tasks: List[ExecutionTask] = []
        self._running_tasks: Dict[str, ExecutionTask] = {}
        self._completed_tasks: Dict[str, ExecutionTask] = {}
        self._task_results: Dict[str, Any] = {}
        
        # Metrics
        self.metrics = PoolMetrics()
        self._lock = asyncio.Lock()
    
    async def submit(
        self,
        node_id: str,
        agent_name: str,
        executor: Callable[[Dict[str, Any], str], Awaitable[Dict[str, Any]]],
        context: Dict[str, Any],
        run_id: str,
        tenant_id: str = "default",
        priority: int = 5,
        dependencies: List[str] = None
    ) -> str:
        """
        提交执行任务
        
        Args:
            node_id: 节点ID
            agent_name: Agent名称
            executor: 执行函数 (async callable)
            context: 执行上下文
            run_id: 运行ID
            tenant_id: 租户ID
            priority: 优先级 (1-10)
            dependencies: 依赖的任务ID列表
            
        Returns:
            task_id: 任务ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task = ExecutionTask(
            task_id=task_id,
            node_id=node_id,
            agent_name=agent_name,
            context=context,
            run_id=run_id,
            tenant_id=tenant_id,
            priority=priority,
            dependencies=dependencies or []
        )
        
        async with self._lock:
            self._pending_tasks.append(task)
            self.metrics.total_tasks += 1
            self.metrics.pending_tasks += 1
        
        # Start execution (will respect semaphore)
        asyncio.create_task(self._execute_task(task, executor))
        
        return task_id
    
    async def _execute_task(
        self,
        task: ExecutionTask,
        executor: Callable[[Dict[str, Any], str], Awaitable[Dict[str, Any]]]
    ):
        """执行单个任务"""
        try:
            # Wait for dependencies
            await self._wait_for_dependencies(task)
            
            # Check backpressure
            await self._check_backpressure()
            
            # Acquire semaphore (backpressure control)
            async with self._semaphore:
                async with self._lock:
                    # Move from pending to running
                    if task in self._pending_tasks:
                        self._pending_tasks.remove(task)
                    self.metrics.pending_tasks = len(self._pending_tasks)
                    
                    task.status = "running"
                    task.started_at = datetime.now()
                    self._running_tasks[task.task_id] = task
                    self.metrics.running_tasks = len(self._running_tasks)
                    
                    # Update max concurrency reached
                    if self.metrics.running_tasks > self.metrics.max_concurrency_reached:
                        self.metrics.max_concurrency_reached = self.metrics.running_tasks
                
                # Execute (outside lock to allow other tasks to proceed)
                result = await executor(task.context, task.run_id)
                
                # Update task
                task.completed_at = datetime.now()
                task.result = result
                task.status = "completed"
                
                # Calculate latency
                if task.started_at and task.completed_at:
                    latency_ms = (task.completed_at - task.started_at).total_seconds() * 1000
                    self.metrics.total_latency_ms += latency_ms
                
                async with self._lock:
                    # Move from running to completed
                    if task.task_id in self._running_tasks:
                        del self._running_tasks[task.task_id]
                    self._completed_tasks[task.task_id] = task
                    self._task_results[task.task_id] = result
                    
                    self.metrics.running_tasks = len(self._running_tasks)
                    self.metrics.completed_tasks = len(self._completed_tasks)
                    self.metrics.avg_latency_ms = (
                        self.metrics.total_latency_ms / self.metrics.completed_tasks
                        if self.metrics.completed_tasks > 0 else 0.0
                    )
                    self.metrics.last_updated = datetime.now()
        
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            task.completed_at = datetime.now()
            
            async with self._lock:
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task
                
                self.metrics.running_tasks = len(self._running_tasks)
                self.metrics.failed_tasks += 1
                self.metrics.last_updated = datetime.now()
    
    async def _wait_for_dependencies(self, task: ExecutionTask):
        """等待依赖任务完成"""
        if not task.dependencies:
            return
        
        # Poll for dependency completion
        max_wait_seconds = 300  # 5 minutes timeout
        wait_interval = 0.1  # 100ms
        elapsed = 0.0
        
        while elapsed < max_wait_seconds:
            all_deps_complete = True
            for dep_id in task.dependencies:
                if dep_id not in self._completed_tasks:
                    all_deps_complete = False
                    break
            
            if all_deps_complete:
                return
            
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
        
        raise TimeoutError(f"Dependencies not completed within {max_wait_seconds}s: {task.dependencies}")
    
    async def _check_backpressure(self):
        """检查背压，必要时等待"""
        while True:
            async with self._lock:
                current_load = len(self._running_tasks) / self.max_concurrency
                if current_load < self.backpressure_threshold:
                    return
                
                # Record backpressure event
                self.metrics.backpressure_events += 1
            
            # Wait before retrying
            await asyncio.sleep(0.1)
    
    async def wait_all(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            Dict[str, Any]: 所有任务的结果
        """
        start_time = datetime.now()
        
        while True:
            async with self._lock:
                if not self._pending_tasks and not self._running_tasks:
                    # All tasks completed
                    return self._task_results
            
            # Check timeout
            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    raise TimeoutError(f"Tasks did not complete within {timeout}s")
            
            await asyncio.sleep(0.1)
    
    async def get_task_status(self, task_id: str) -> Optional[ExecutionTask]:
        """获取任务状态"""
        async with self._lock:
            # Check all task stores
            for task in self._pending_tasks:
                if task.task_id == task_id:
                    return task
            
            if task_id in self._running_tasks:
                return self._running_tasks[task_id]
            
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]
            
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅对pending任务有效）"""
        async with self._lock:
            for task in self._pending_tasks:
                if task.task_id == task_id:
                    self._pending_tasks.remove(task)
                    task.status = "cancelled"
                    task.completed_at = datetime.now()
                    self._completed_tasks[task_id] = task
                    
                    self.metrics.pending_tasks = len(self._pending_tasks)
                    self.metrics.failed_tasks += 1
                    return True
            
            return False
    
    def get_metrics(self) -> PoolMetrics:
        """获取池指标"""
        return self.metrics
    
    async def save_concurrency_report(self, run_id: str):
        """保存并发执行报告"""
        report = {
            "run_id": run_id,
            "pool_config": {
                "max_concurrency": self.max_concurrency,
                "backpressure_threshold": self.backpressure_threshold
            },
            "metrics": {
                "total_tasks": self.metrics.total_tasks,
                "completed_tasks": self.metrics.completed_tasks,
                "failed_tasks": self.metrics.failed_tasks,
                "avg_latency_ms": self.metrics.avg_latency_ms,
                "max_concurrency_reached": self.metrics.max_concurrency_reached,
                "backpressure_events": self.metrics.backpressure_events
            },
            "tasks": [
                {
                    "task_id": task.task_id,
                    "node_id": task.node_id,
                    "agent_name": task.agent_name,
                    "tenant_id": task.tenant_id,
                    "status": task.status,
                    "priority": task.priority,
                    "latency_ms": (
                        (task.completed_at - task.started_at).total_seconds() * 1000
                        if task.started_at and task.completed_at else None
                    ),
                    "error": task.error
                }
                for task in self._completed_tasks.values()
            ],
            "generated_at": datetime.now().isoformat()
        }
        
        report_path = os.path.join(self.artifacts_dir, f"concurrency_report_{run_id}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report_path


# Global pool instance
_global_pool: Optional[ExecutionPool] = None


def get_execution_pool(
    max_concurrency: int = 10,
    backpressure_threshold: float = 0.8
) -> ExecutionPool:
    """获取全局执行池"""
    global _global_pool
    if _global_pool is None:
        _global_pool = ExecutionPool(
            max_concurrency=max_concurrency,
            backpressure_threshold=backpressure_threshold
        )
    return _global_pool

