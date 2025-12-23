"""
Worker: 分布式任务执行器
从 TaskQueue 获取任务并执行
"""
import asyncio
import json
import os
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import uuid
import traceback

from runtime.dispatcher.task_queue import TaskQueue, QueuedTask


class Worker:
    """
    分布式 Worker
    
    Features:
    - Pull tasks from TaskQueue
    - Execute with timeout
    - Report results back to queue
    - Record execution traces
    """
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        task_queue: TaskQueue = None,
        executor: Callable[[QueuedTask], Awaitable[Dict[str, Any]]] = None,
        artifacts_dir: str = "artifacts/execution",
        max_tasks: int = 0,  # 0 = unlimited
        shutdown_on_empty: bool = False
    ):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.task_queue = task_queue
        self.executor = executor
        self.artifacts_dir = artifacts_dir
        self.max_tasks = max_tasks
        self.shutdown_on_empty = shutdown_on_empty
        
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # State
        self._running = False
        self._tasks_executed = 0
        self._tasks_succeeded = 0
        self._tasks_failed = 0
        self._start_time: Optional[datetime] = None
        self._execution_traces: list = []
    
    async def start(self):
        """启动 Worker"""
        if self._running:
            return
        
        self._running = True
        self._start_time = datetime.now()
        
        print(f"[Worker {self.worker_id}] Starting...")
        
        while self._running:
            try:
                # Check max_tasks limit
                if self.max_tasks > 0 and self._tasks_executed >= self.max_tasks:
                    print(f"[Worker {self.worker_id}] Max tasks reached ({self.max_tasks}), shutting down.")
                    break
                
                # Dequeue task with timeout
                task = await self.task_queue.dequeue(self.worker_id, timeout=5.0)
                
                if task is None:
                    # No task available
                    if self.shutdown_on_empty:
                        queue_size = await self.task_queue.get_queue_size()
                        if queue_size == 0:
                            print(f"[Worker {self.worker_id}] Queue empty, shutting down.")
                            break
                    continue
                
                # Execute task
                await self._execute_task(task)
                
            except asyncio.CancelledError:
                print(f"[Worker {self.worker_id}] Cancelled.")
                break
            except Exception as e:
                print(f"[Worker {self.worker_id}] Error: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)  # Backoff on error
        
        self._running = False
        
        # Save worker summary
        await self._save_worker_summary()
        
        print(f"[Worker {self.worker_id}] Stopped. Executed {self._tasks_executed} tasks.")
    
    async def _execute_task(self, task: QueuedTask):
        """执行单个任务"""
        trace_entry = {
            "worker_id": self.worker_id,
            "task_id": task.task_id,
            "run_id": task.run_id,
            "tenant_id": task.tenant_id,
            "node_id": task.node_id,
            "agent_name": task.agent_name,
            "started_at": datetime.now().isoformat(),
            "status": "running"
        }
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.executor(task),
                timeout=task.timeout_sec
            )
            
            # ACK
            await self.task_queue.ack(task.task_id, result)
            
            trace_entry["status"] = "completed"
            trace_entry["completed_at"] = datetime.now().isoformat()
            trace_entry["result_summary"] = {
                "decision": result.get("decision"),
                "success": result.get("decision") not in ["terminate", "failed"]
            }
            
            self._tasks_succeeded += 1
            
        except asyncio.TimeoutError:
            error = f"Task timeout after {task.timeout_sec}s"
            await self.task_queue.nack(task.task_id, error, retry=True)
            
            trace_entry["status"] = "timeout"
            trace_entry["error"] = error
            trace_entry["completed_at"] = datetime.now().isoformat()
            
            self._tasks_failed += 1
            
        except Exception as e:
            error = f"Execution error: {str(e)}"
            await self.task_queue.nack(task.task_id, error, retry=True)
            
            trace_entry["status"] = "failed"
            trace_entry["error"] = error
            trace_entry["traceback"] = traceback.format_exc()
            trace_entry["completed_at"] = datetime.now().isoformat()
            
            self._tasks_failed += 1
        
        self._tasks_executed += 1
        self._execution_traces.append(trace_entry)
        
        # Save trace incrementally
        await self._save_execution_trace(trace_entry)
    
    async def stop(self):
        """停止 Worker"""
        print(f"[Worker {self.worker_id}] Stopping...")
        self._running = False
    
    async def _save_execution_trace(self, trace_entry: Dict[str, Any]):
        """保存执行 trace"""
        trace_file = os.path.join(
            self.artifacts_dir,
            f"distributed_trace_{self.worker_id}.jsonl"
        )
        
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
    
    async def _save_worker_summary(self):
        """保存 Worker 汇总"""
        if not self._start_time:
            return
        
        end_time = datetime.now()
        duration_sec = (end_time - self._start_time).total_seconds()
        
        summary = {
            "worker_id": self.worker_id,
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_sec": duration_sec,
            "tasks_executed": self._tasks_executed,
            "tasks_succeeded": self._tasks_succeeded,
            "tasks_failed": self._tasks_failed,
            "success_rate": (
                self._tasks_succeeded / self._tasks_executed
                if self._tasks_executed > 0 else 0.0
            ),
            "throughput_tasks_per_sec": (
                self._tasks_executed / duration_sec
                if duration_sec > 0 else 0.0
            )
        }
        
        summary_file = os.path.join(
            self.artifacts_dir,
            f"worker_summary_{self.worker_id}.json"
        )
        
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 Worker 统计信息"""
        if not self._start_time:
            return {}
        
        duration_sec = (datetime.now() - self._start_time).total_seconds()
        
        return {
            "worker_id": self.worker_id,
            "running": self._running,
            "uptime_sec": duration_sec,
            "tasks_executed": self._tasks_executed,
            "tasks_succeeded": self._tasks_succeeded,
            "tasks_failed": self._tasks_failed,
            "success_rate": (
                self._tasks_succeeded / self._tasks_executed
                if self._tasks_executed > 0 else 0.0
            )
        }


class WorkerPool:
    """Worker 池管理器"""
    
    def __init__(
        self,
        num_workers: int,
        task_queue: TaskQueue,
        executor: Callable[[QueuedTask], Awaitable[Dict[str, Any]]],
        artifacts_dir: str = "artifacts/execution"
    ):
        self.num_workers = num_workers
        self.task_queue = task_queue
        self.executor = executor
        self.artifacts_dir = artifacts_dir
        
        self.workers: list[Worker] = []
        self.worker_tasks: list[asyncio.Task] = []
    
    async def start(self):
        """启动所有 Worker"""
        for i in range(self.num_workers):
            worker = Worker(
                worker_id=f"worker_{i}",
                task_queue=self.task_queue,
                executor=self.executor,
                artifacts_dir=self.artifacts_dir,
                shutdown_on_empty=False
            )
            self.workers.append(worker)
            
            task = asyncio.create_task(worker.start())
            self.worker_tasks.append(task)
        
        print(f"[WorkerPool] Started {self.num_workers} workers.")
    
    async def stop(self):
        """停止所有 Worker"""
        for worker in self.workers:
            await worker.stop()
        
        # Wait for all workers to finish
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        print(f"[WorkerPool] All workers stopped.")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取 Pool 统计信息"""
        total_executed = sum(w._tasks_executed for w in self.workers)
        total_succeeded = sum(w._tasks_succeeded for w in self.workers)
        total_failed = sum(w._tasks_failed for w in self.workers)
        
        return {
            "num_workers": self.num_workers,
            "total_tasks_executed": total_executed,
            "total_tasks_succeeded": total_succeeded,
            "total_tasks_failed": total_failed,
            "success_rate": (
                total_succeeded / total_executed
                if total_executed > 0 else 0.0
            ),
            "workers": [w.get_stats() for w in self.workers]
        }

