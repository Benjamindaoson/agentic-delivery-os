"""
Control Plane - Distributed execution scheduler
L6 Component: Distributed Architecture
"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
import json
import os


class WorkerNode(BaseModel):
    """Worker node registration"""
    worker_id: str
    host: str
    port: int
    capabilities: List[str]
    max_concurrent_tasks: int
    registered_at: datetime
    last_heartbeat: datetime
    status: str  # active | idle | busy | offline
    current_tasks: List[str] = []


class TaskLease(BaseModel):
    """Task lease for distributed execution"""
    lease_id: str
    task_id: str
    worker_id: str
    tenant_id: str
    leased_at: datetime
    expires_at: datetime
    heartbeat_interval: int = 30  # seconds
    status: str  # leased | executing | completed | failed | expired


class ControlPlane:
    """
    Distributed execution control plane
    Manages worker registration, task scheduling, lease management
    """
    
    def __init__(
        self,
        lease_duration: int = 300,  # 5 minutes
        heartbeat_timeout: int = 60,  # 1 minute
        artifacts_path: str = "artifacts/distributed"
    ):
        self.lease_duration = lease_duration
        self.heartbeat_timeout = heartbeat_timeout
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # State
        self.workers: Dict[str, WorkerNode] = {}
        self.leases: Dict[str, TaskLease] = {}
        self.pending_tasks: List[Dict[str, Any]] = []
        
        # Statistics
        self.stats = {
            "total_tasks_scheduled": 0,
            "total_leases_granted": 0,
            "total_lease_expirations": 0,
            "active_workers": 0
        }
    
    def register_worker(
        self,
        host: str,
        port: int,
        capabilities: List[str],
        max_concurrent_tasks: int = 5,
        worker_id: Optional[str] = None
    ) -> str:
        """Register a new worker node"""
        if worker_id is None:
            worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        
        worker = WorkerNode(
            worker_id=worker_id,
            host=host,
            port=port,
            capabilities=capabilities,
            max_concurrent_tasks=max_concurrent_tasks,
            registered_at=datetime.now(),
            last_heartbeat=datetime.now(),
            status="idle"
        )
        
        self.workers[worker_id] = worker
        self.stats["active_workers"] = len([w for w in self.workers.values() if w.status != "offline"])
        
        return worker_id
    
    def heartbeat(self, worker_id: str) -> bool:
        """Process worker heartbeat"""
        if worker_id not in self.workers:
            return False
        
        self.workers[worker_id].last_heartbeat = datetime.now()
        return True
    
    def schedule_task(
        self,
        task: Dict[str, Any],
        tenant_id: str = "default",
        required_capabilities: List[str] = None
    ) -> Optional[str]:
        """
        Schedule a task for execution
        Returns: lease_id if scheduled, None if no workers available
        """
        if required_capabilities is None:
            required_capabilities = []
        
        # Find available worker
        available_workers = [
            w for w in self.workers.values()
            if w.status in ["idle", "active"] and
            len(w.current_tasks) < w.max_concurrent_tasks and
            all(cap in w.capabilities for cap in required_capabilities)
        ]
        
        if not available_workers:
            # Queue task
            self.pending_tasks.append({
                "task": task,
                "tenant_id": tenant_id,
                "required_capabilities": required_capabilities
            })
            return None
        
        # Select worker (simple: least loaded)
        worker = min(available_workers, key=lambda w: len(w.current_tasks))
        
        # Create lease
        lease_id = f"lease_{uuid.uuid4().hex[:12]}"
        task_id = task.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
        
        lease = TaskLease(
            lease_id=lease_id,
            task_id=task_id,
            worker_id=worker.worker_id,
            tenant_id=tenant_id,
            leased_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.lease_duration),
            status="leased"
        )
        
        self.leases[lease_id] = lease
        worker.current_tasks.append(task_id)
        worker.status = "busy" if len(worker.current_tasks) >= worker.max_concurrent_tasks else "active"
        
        self.stats["total_tasks_scheduled"] += 1
        self.stats["total_leases_granted"] += 1
        
        return lease_id
    
    def complete_task(self, lease_id: str, result: Any):
        """Mark task as completed"""
        if lease_id not in self.leases:
            return False
        
        lease = self.leases[lease_id]
        lease.status = "completed"
        
        # Update worker
        if lease.worker_id in self.workers:
            worker = self.workers[lease.worker_id]
            if lease.task_id in worker.current_tasks:
                worker.current_tasks.remove(lease.task_id)
            worker.status = "idle" if len(worker.current_tasks) == 0 else "active"
        
        return True
    
    def check_expired_leases(self):
        """Check and mark expired leases"""
        now = datetime.now()
        
        for lease_id, lease in self.leases.items():
            if lease.status == "leased" and lease.expires_at < now:
                lease.status = "expired"
                self.stats["total_lease_expirations"] += 1
                
                # Release worker
                if lease.worker_id in self.workers:
                    worker = self.workers[lease.worker_id]
                    if lease.task_id in worker.current_tasks:
                        worker.current_tasks.remove(lease.task_id)
                    worker.status = "idle" if len(worker.current_tasks) == 0 else "active"
    
    def check_dead_workers(self):
        """Check for workers that haven't sent heartbeats"""
        now = datetime.now()
        timeout = timedelta(seconds=self.heartbeat_timeout)
        
        for worker_id, worker in self.workers.items():
            if worker.status != "offline" and (now - worker.last_heartbeat) > timeout:
                worker.status = "offline"
                self.stats["active_workers"] = len([w for w in self.workers.values() if w.status != "offline"])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get control plane statistics"""
        return {
            "statistics": dict(self.stats),
            "workers": {
                "total": len(self.workers),
                "active": len([w for w in self.workers.values() if w.status != "offline"]),
                "busy": len([w for w in self.workers.values() if w.status == "busy"]),
                "idle": len([w for w in self.workers.values() if w.status == "idle"])
            },
            "tasks": {
                "pending": len(self.pending_tasks),
                "active_leases": len([l for l in self.leases.values() if l.status in ["leased", "executing"]])
            }
        }


# Global control plane
_control_plane: Optional[ControlPlane] = None

def get_control_plane() -> ControlPlane:
    """Get global control plane"""
    global _control_plane
    if _control_plane is None:
        _control_plane = ControlPlane()
    return _control_plane



