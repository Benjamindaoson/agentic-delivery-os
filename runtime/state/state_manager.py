"""
State Manager: 状态治理
至少包含：IDLE, SPEC_READY, RUNNING, FAILED, COMPLETED
要求：所有Agent必须通过state读写交互
"""
from typing import Optional, Dict, Any
from enum import Enum
import aiosqlite
import json
import os

class TaskState(str, Enum):
    IDLE = "IDLE"
    SPEC_READY = "SPEC_READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class TaskStateRecord:
    def __init__(self, task_id: str, state: TaskState, error: Optional[str] = None, progress: Optional[Dict] = None, context: Optional[Dict] = None):
        self.task_id = task_id
        self.state = state
        self.error = error
        self.progress = progress or {}
        self.context = context or {}

class StateManager:
    def __init__(self, db_path: str = "runtime/state/tasks.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async def initialize(self):
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            # 任务表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    error TEXT,
                    progress TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 状态迁移记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            await db.commit()
    
    async def create_task(self, task_id: str, spec: Dict[str, Any]):
        """创建任务"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tasks (task_id, state, context)
                VALUES (?, ?, ?)
            """, (task_id, TaskState.IDLE.value, json.dumps({"spec": spec})))
            await db.commit()
    
    async def update_task_state(self, task_id: str, state: str, error: Optional[str] = None, progress: Optional[Dict] = None, reason: Optional[str] = None):
        """更新任务状态，并记录状态迁移"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取当前状态
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT state FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
                row = await cursor.fetchone()
                from_state = row["state"] if row else None
            
            # 更新任务状态
            progress_json = json.dumps(progress) if progress else None
            await db.execute("""
                UPDATE tasks
                SET state = ?, error = ?, progress = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (state, error, progress_json, task_id))
            
            # 记录状态迁移
            await db.execute("""
                INSERT INTO state_transitions (task_id, from_state, to_state, reason)
                VALUES (?, ?, ?, ?)
            """, (task_id, from_state, state, reason or f"State transition to {state}"))
            
            await db.commit()
    
    async def get_task_state(self, task_id: str) -> Optional[TaskStateRecord]:
        """获取任务状态"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT task_id, state, error, progress, context
                FROM tasks
                WHERE task_id = ?
            """, (task_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return TaskStateRecord(
                    task_id=row["task_id"],
                    state=TaskState(row["state"]),
                    error=row["error"],
                    progress=json.loads(row["progress"]) if row["progress"] else {},
                    context=json.loads(row["context"]) if row["context"] else {}
                )
    
    async def get_task_context(self, task_id: str) -> Dict[str, Any]:
        """获取任务上下文"""
        state_record = await self.get_task_state(task_id)
        if not state_record:
            return {}
        return state_record.context
    
    async def update_task_context(self, task_id: str, context: Dict[str, Any]):
        """更新任务上下文"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tasks
                SET context = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (json.dumps(context), task_id))
            await db.commit()
    
    async def get_state_transitions(self, task_id: str) -> list:
        """获取任务的状态迁移记录"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT from_state, to_state, reason, timestamp
                FROM state_transitions
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """, (task_id,)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "from_state": row["from_state"],
                        "to_state": row["to_state"],
                        "reason": row["reason"],
                        "timestamp": row["timestamp"]
                    }
                    for row in rows
                ]

