"""
TaskQueue: 分布式任务队列
支持 in-memory 和 Redis 两种实现
"""
import asyncio
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import uuid


class TaskPriority(int, Enum):
    """任务优先级"""
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BATCH = 9


@dataclass
class QueuedTask:
    """队列任务"""
    task_id: str
    run_id: str
    tenant_id: str
    node_id: str
    agent_name: str
    context: Dict[str, Any]
    priority: int = TaskPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    timeout_sec: int = 300
    created_at: str = ""
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueuedTask':
        return cls(**data)


class TaskQueue(ABC):
    """任务队列抽象接口"""
    
    @abstractmethod
    async def enqueue(self, task: QueuedTask) -> bool:
        """入队"""
        pass
    
    @abstractmethod
    async def dequeue(self, worker_id: str) -> Optional[QueuedTask]:
        """出队（阻塞直到有任务或超时）"""
        pass
    
    @abstractmethod
    async def ack(self, task_id: str, result: Dict[str, Any]) -> bool:
        """确认任务完成"""
        pass
    
    @abstractmethod
    async def nack(self, task_id: str, error: str, retry: bool = True) -> bool:
        """标记任务失败"""
        pass
    
    @abstractmethod
    async def get_queue_size(self) -> int:
        """获取队列大小"""
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        pass


class InMemoryTaskQueue(TaskQueue):
    """内存任务队列（适用于单机）"""
    
    def __init__(self, artifacts_dir: str = "artifacts/execution"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Priority queues (sorted by priority)
        self._pending_queues: Dict[int, List[QueuedTask]] = {p.value: [] for p in TaskPriority}
        self._in_progress: Dict[str, QueuedTask] = {}
        self._completed: Dict[str, Dict[str, Any]] = {}
        self._failed: Dict[str, Dict[str, Any]] = {}
        
        self._lock = asyncio.Lock()
        self._has_tasks = asyncio.Event()
    
    async def enqueue(self, task: QueuedTask) -> bool:
        """入队"""
        async with self._lock:
            priority = task.priority
            if priority not in self._pending_queues:
                priority = TaskPriority.NORMAL
            
            self._pending_queues[priority].append(task)
            self._has_tasks.set()
            
            # Save to disk for persistence
            await self._persist_queue_state()
            
            return True
    
    async def dequeue(self, worker_id: str, timeout: float = 30.0) -> Optional[QueuedTask]:
        """
        出队（阻塞直到有任务或超时）
        
        优先级策略：从高优先级队列依次尝试
        """
        try:
            # Wait for tasks with timeout
            await asyncio.wait_for(self._has_tasks.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        
        async with self._lock:
            # Try to get task from highest priority queue first
            for priority in sorted(self._pending_queues.keys()):
                if self._pending_queues[priority]:
                    task = self._pending_queues[priority].pop(0)
                    task.started_at = datetime.now().isoformat()
                    self._in_progress[task.task_id] = task
                    
                    # Update event state
                    total_pending = sum(len(q) for q in self._pending_queues.values())
                    if total_pending == 0:
                        self._has_tasks.clear()
                    
                    await self._persist_queue_state()
                    return task
            
            # No tasks found (race condition)
            self._has_tasks.clear()
            return None
    
    async def ack(self, task_id: str, result: Dict[str, Any]) -> bool:
        """确认任务完成"""
        async with self._lock:
            if task_id not in self._in_progress:
                return False
            
            task = self._in_progress.pop(task_id)
            task.completed_at = datetime.now().isoformat()
            
            self._completed[task_id] = {
                "task": task.to_dict(),
                "result": result,
                "completed_at": task.completed_at
            }
            
            await self._persist_task_result(task_id, result, success=True)
            return True
    
    async def nack(self, task_id: str, error: str, retry: bool = True) -> bool:
        """标记任务失败"""
        async with self._lock:
            if task_id not in self._in_progress:
                return False
            
            task = self._in_progress.pop(task_id)
            task.retry_count += 1
            
            # Retry if allowed
            if retry and task.retry_count < task.max_retries:
                # Re-enqueue with lower priority
                task.priority = min(task.priority + 1, TaskPriority.BATCH)
                self._pending_queues[task.priority].append(task)
                self._has_tasks.set()
            else:
                # Mark as failed
                self._failed[task_id] = {
                    "task": task.to_dict(),
                    "error": error,
                    "retry_count": task.retry_count,
                    "failed_at": datetime.now().isoformat()
                }
                
                await self._persist_task_result(task_id, {"error": error}, success=False)
            
            await self._persist_queue_state()
            return True
    
    async def get_queue_size(self) -> int:
        """获取队列大小"""
        async with self._lock:
            return sum(len(q) for q in self._pending_queues.values())
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        async with self._lock:
            # Check in-progress
            if task_id in self._in_progress:
                return {
                    "status": "in_progress",
                    "task": self._in_progress[task_id].to_dict()
                }
            
            # Check completed
            if task_id in self._completed:
                return {
                    "status": "completed",
                    **self._completed[task_id]
                }
            
            # Check failed
            if task_id in self._failed:
                return {
                    "status": "failed",
                    **self._failed[task_id]
                }
            
            # Check pending
            for queue in self._pending_queues.values():
                for task in queue:
                    if task.task_id == task_id:
                        return {
                            "status": "pending",
                            "task": task.to_dict()
                        }
            
            return None
    
    async def _persist_queue_state(self):
        """持久化队列状态"""
        state = {
            "pending": {
                priority: [task.to_dict() for task in tasks]
                for priority, tasks in self._pending_queues.items()
            },
            "in_progress": {
                task_id: task.to_dict()
                for task_id, task in self._in_progress.items()
            },
            "last_updated": datetime.now().isoformat()
        }
        
        state_path = os.path.join(self.artifacts_dir, "queue_state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    async def _persist_task_result(self, task_id: str, result: Dict[str, Any], success: bool):
        """持久化任务结果"""
        result_data = {
            "task_id": task_id,
            "success": success,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        result_path = os.path.join(self.artifacts_dir, f"task_result_{task_id}.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)


class RedisTaskQueue(TaskQueue):
    """
    Redis 任务队列（适用于分布式）
    
    Note: 这是一个基本实现框架，生产环境需要使用 redis-py 或 aioredis
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", key_prefix: str = "task_queue"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        # TODO: Initialize Redis connection
        # self.redis = await aioredis.from_url(redis_url)
        raise NotImplementedError("RedisTaskQueue requires redis-py or aioredis. Use InMemoryTaskQueue for now.")
    
    async def enqueue(self, task: QueuedTask) -> bool:
        """入队到 Redis"""
        # TODO: ZADD to priority queue
        pass
    
    async def dequeue(self, worker_id: str, timeout: float = 30.0) -> Optional[QueuedTask]:
        """从 Redis 出队"""
        # TODO: BZPOPMIN with timeout
        pass
    
    async def ack(self, task_id: str, result: Dict[str, Any]) -> bool:
        """ACK 到 Redis"""
        # TODO: Move from in-progress to completed
        pass
    
    async def nack(self, task_id: str, error: str, retry: bool = True) -> bool:
        """NACK 到 Redis"""
        # TODO: Move from in-progress to failed or retry queue
        pass
    
    async def get_queue_size(self) -> int:
        """获取 Redis 队列大小"""
        # TODO: ZCARD
        pass
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从 Redis 获取任务状态"""
        # TODO: Check multiple Redis keys
        pass


def create_task_queue(queue_type: str = "memory", **kwargs) -> TaskQueue:
    """
    创建任务队列
    
    Args:
        queue_type: "memory" or "redis"
        **kwargs: 队列配置参数
        
    Returns:
        TaskQueue 实例
    """
    if queue_type == "memory":
        return InMemoryTaskQueue(**kwargs)
    elif queue_type == "redis":
        return RedisTaskQueue(**kwargs)
    else:
        raise ValueError(f"Unknown queue type: {queue_type}")

