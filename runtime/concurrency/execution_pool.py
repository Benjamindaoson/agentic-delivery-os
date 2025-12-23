"""
Execution Pool - Concurrent execution management for parallel DAG nodes
L6 Component: Scale Layer - Concurrency
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
import json
import os


@dataclass
class ExecutionTask:
    """Single execution task"""
    task_id: str
    node_id: str
    run_id: str
    tenant_id: str
    agent_id: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: int = 5
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ExecutionStats:
    """Pool execution statistics"""
    total_submitted: int = 0
    total_completed: int = 0
    total_failed: int = 0
    active_tasks: int = 0
    avg_latency_ms: float = 0.0
    peak_concurrency: int = 0


class ExecutionPool:
    """
    Manages concurrent execution of DAG nodes and agent tasks
    Supports parallel execution with resource limits
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        max_concurrent_per_tenant: int = 5,
        max_concurrent_per_agent: int = 2,
        artifacts_path: str = "artifacts/concurrency"
    ):
        self.max_workers = max_workers
        self.max_concurrent_per_tenant = max_concurrent_per_tenant
        self.max_concurrent_per_agent = max_concurrent_per_agent
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Thread pool for CPU-bound tasks
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Task tracking
        self.pending_tasks: Dict[str, ExecutionTask] = {}
        self.active_tasks: Dict[str, ExecutionTask] = {}
        self.completed_tasks: Dict[str, ExecutionTask] = {}
        
        # Concurrency limits
        self.tenant_active_count: Dict[str, int] = {}
        self.agent_active_count: Dict[str, int] = {}
        
        # Statistics
        self.stats = ExecutionStats()
        
        # Async event loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
    
    def submit_task(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        run_id: str = None,
        tenant_id: str = "default",
        agent_id: str = "default",
        node_id: str = None,
        priority: int = 5
    ) -> str:
        """
        Submit a task for execution
        Returns: task_id
        """
        if kwargs is None:
            kwargs = {}
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task = ExecutionTask(
            task_id=task_id,
            node_id=node_id or task_id,
            run_id=run_id or f"run_{uuid.uuid4().hex[:8]}",
            tenant_id=tenant_id,
            agent_id=agent_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority
        )
        
        self.pending_tasks[task_id] = task
        self.stats.total_submitted += 1
        
        return task_id
    
    def submit_dag_nodes(
        self,
        dag_nodes: List[Dict[str, Any]],
        run_id: str,
        tenant_id: str = "default"
    ) -> List[str]:
        """
        Submit multiple DAG nodes for parallel execution
        Returns: list of task_ids
        """
        task_ids = []
        
        for node in dag_nodes:
            # Check if node can be executed in parallel
            if node.get("parallelizable", False):
                task_id = self.submit_task(
                    func=self._execute_node,
                    kwargs={"node": node},
                    run_id=run_id,
                    tenant_id=tenant_id,
                    agent_id=node.get("agent_id", "default"),
                    node_id=node.get("node_id", "unknown"),
                    priority=node.get("priority", 5)
                )
                task_ids.append(task_id)
        
        return task_ids
    
    def _execute_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single DAG node (placeholder)"""
        import time
        time.sleep(0.1)  # Simulate execution
        return {
            "node_id": node.get("node_id"),
            "status": "completed",
            "output": f"Result from {node.get('node_id')}"
        }
    
    async def execute_async(self, task_id: str) -> Any:
        """Execute a task asynchronously"""
        if task_id not in self.pending_tasks:
            raise ValueError(f"Task {task_id} not found")
        
        task = self.pending_tasks.pop(task_id)
        
        # Check concurrency limits
        while not self._can_execute(task):
            await asyncio.sleep(0.1)  # Backpressure
        
        # Move to active
        self.active_tasks[task_id] = task
        self._increment_active_counts(task)
        self.stats.active_tasks = len(self.active_tasks)
        self.stats.peak_concurrency = max(self.stats.peak_concurrency, self.stats.active_tasks)
        
        task.started_at = datetime.now()
        
        # Execute in thread pool
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                task.func,
                *task.args,
                **task.kwargs
            )
            
            task.result = result
            task.completed_at = datetime.now()
            self.stats.total_completed += 1
            
        except Exception as e:
            task.error = str(e)
            task.completed_at = datetime.now()
            self.stats.total_failed += 1
        
        finally:
            # Move to completed
            self.active_tasks.pop(task_id, None)
            self.completed_tasks[task_id] = task
            self._decrement_active_counts(task)
            self.stats.active_tasks = len(self.active_tasks)
            
            # Update avg latency
            if task.started_at and task.completed_at:
                latency = (task.completed_at - task.started_at).total_seconds() * 1000
                n = self.stats.total_completed + self.stats.total_failed
                self.stats.avg_latency_ms = (
                    (self.stats.avg_latency_ms * (n - 1) + latency) / n
                )
        
        return task.result
    
    def execute_sync(self, task_id: str) -> Any:
        """Execute a task synchronously"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        return self.loop.run_until_complete(self.execute_async(task_id))
    
    async def execute_many(self, task_ids: List[str]) -> List[Any]:
        """Execute multiple tasks concurrently"""
        tasks = [self.execute_async(task_id) for task_id in task_ids]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def execute_many_sync(self, task_ids: List[str]) -> List[Any]:
        """Execute multiple tasks synchronously"""
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        return self.loop.run_until_complete(self.execute_many(task_ids))
    
    def _can_execute(self, task: ExecutionTask) -> bool:
        """Check if task can be executed given current limits"""
        tenant_count = self.tenant_active_count.get(task.tenant_id, 0)
        agent_count = self.agent_active_count.get(task.agent_id, 0)
        
        return (
            len(self.active_tasks) < self.max_workers and
            tenant_count < self.max_concurrent_per_tenant and
            agent_count < self.max_concurrent_per_agent
        )
    
    def _increment_active_counts(self, task: ExecutionTask):
        """Increment active counters"""
        self.tenant_active_count[task.tenant_id] = (
            self.tenant_active_count.get(task.tenant_id, 0) + 1
        )
        self.agent_active_count[task.agent_id] = (
            self.agent_active_count.get(task.agent_id, 0) + 1
        )
    
    def _decrement_active_counts(self, task: ExecutionTask):
        """Decrement active counters"""
        self.tenant_active_count[task.tenant_id] = max(
            0, self.tenant_active_count.get(task.tenant_id, 0) - 1
        )
        self.agent_active_count[task.agent_id] = max(
            0, self.agent_active_count.get(task.agent_id, 0) - 1
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            "total_submitted": self.stats.total_submitted,
            "total_completed": self.stats.total_completed,
            "total_failed": self.stats.total_failed,
            "active_tasks": self.stats.active_tasks,
            "pending_tasks": len(self.pending_tasks),
            "avg_latency_ms": self.stats.avg_latency_ms,
            "peak_concurrency": self.stats.peak_concurrency,
            "tenant_active": dict(self.tenant_active_count),
            "agent_active": dict(self.agent_active_count)
        }
    
    def save_stats(self):
        """Persist statistics"""
        path = os.path.join(self.artifacts_path, "execution_pool_stats.json")
        with open(path, 'w') as f:
            json.dump(self.get_stats(), f, indent=2)
    
    def shutdown(self):
        """Shutdown the pool"""
        self.executor.shutdown(wait=True)
        self.save_stats()


# Global pool instance
_pool: Optional[ExecutionPool] = None

def get_execution_pool(
    max_workers: int = 10,
    max_concurrent_per_tenant: int = 5,
    max_concurrent_per_agent: int = 2
) -> ExecutionPool:
    """Get global execution pool"""
    global _pool
    if _pool is None:
        _pool = ExecutionPool(
            max_workers=max_workers,
            max_concurrent_per_tenant=max_concurrent_per_tenant,
            max_concurrent_per_agent=max_concurrent_per_agent
        )
    return _pool



