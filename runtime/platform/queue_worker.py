"""
Queue & Worker: 并发隔离 + 限流
目标：从"单机跑得动"升级为"多任务可运营"
"""
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import time

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

@dataclass
class Task:
    """任务对象"""
    task_id: str
    spec: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class TaskQueue:
    """任务队列"""
    
    def __init__(self, max_concurrent: int = 3):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def enqueue(self, task: Task):
        """入队"""
        await self.queue.put(task)
    
    async def dequeue(self) -> Optional[Task]:
        """出队"""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None
    
    def get_running_count(self) -> int:
        """获取运行中任务数"""
        return len([t for t in self.running_tasks.values() if t.status == TaskStatus.RUNNING])
    
    def can_accept_new(self) -> bool:
        """是否可以接受新任务"""
        return self.get_running_count() < self.max_concurrent

class Worker:
    """Worker：执行任务"""
    
    def __init__(
        self,
        queue: TaskQueue,
        executor: Callable[[str, Dict[str, Any]], Any],
        rate_limiter: Optional[Any] = None
    ):
        self.queue = queue
        self.executor = executor
        self.rate_limiter = rate_limiter
        self.running = False
    
    async def start(self):
        """启动 Worker"""
        self.running = True
        while self.running:
            # 检查并发限制
            if not self.queue.can_accept_new():
                await asyncio.sleep(0.5)
                continue
            
            # 出队
            task = await self.queue.dequeue()
            if task is None:
                await asyncio.sleep(0.1)
                continue
            
            # 执行任务（带并发限制）
            async with self.queue.semaphore:
                asyncio.create_task(self._execute_task(task))
    
    async def _execute_task(self, task: Task):
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        self.queue.running_tasks[task.task_id] = task
        
        try:
            # 应用限流（如果有）
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            
            # 执行
            await self.executor(task.task_id, task.spec)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
        finally:
            # 移动到完成列表
            self.queue.completed_tasks[task.task_id] = task
            if task.task_id in self.queue.running_tasks:
                del self.queue.running_tasks[task.task_id]
    
    def stop(self):
        """停止 Worker"""
        self.running = False

class RateLimiter:
    """限流器：LLM / Tool 调用限流"""
    
    def __init__(self, max_calls_per_second: float = 10.0):
        self.max_calls_per_second = max_calls_per_second
        self.call_times: list = []
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """获取许可"""
        async with self.lock:
            now = time.time()
            # 清理过期记录
            self.call_times = [t for t in self.call_times if now - t < 1.0]
            
            # 检查是否超过限制
            if len(self.call_times) >= self.max_calls_per_second:
                # 等待直到可以调用
                wait_time = 1.0 - (now - self.call_times[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # 重新清理
                    now = time.time()
                    self.call_times = [t for t in self.call_times if now - t < 1.0]
            
            # 记录调用时间
            self.call_times.append(time.time())


