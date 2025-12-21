"""
Postgres-backed StateManager (async) using asyncpg.
Provides same interface as runtime/state/state_manager.py.
"""
from typing import Optional, Dict, Any
import asyncpg
import os
import json

class PostgresStateManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None

    async def initialize(self):
        """Initialize connection pool and ensure tables exist."""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    error TEXT,
                    progress JSONB,
                    context JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    async def create_task(self, task_id: str, spec: Dict[str, Any]):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO tasks (task_id, state, context) VALUES ($1, $2, $3) ON CONFLICT (task_id) DO NOTHING",
                task_id,
                "IDLE",
                json.dumps({"spec": spec}),
            )

    async def update_task_state(self, task_id: str, state: str, error: Optional[str] = None, progress: Optional[Dict] = None, reason: Optional[str] = None):
        progress_json = json.dumps(progress) if progress else None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT state FROM tasks WHERE task_id = $1", task_id)
            from_state = row["state"] if row else None
            await conn.execute(
                "INSERT INTO state_transitions (task_id, from_state, to_state, reason) VALUES ($1,$2,$3,$4)",
                task_id,
                from_state,
                state,
                reason or f"State transition to {state}",
            )
            await conn.execute(
                "UPDATE tasks SET state = $1, error = $2, progress = $3, updated_at = CURRENT_TIMESTAMP WHERE task_id = $4",
                state,
                error,
                progress_json,
                task_id,
            )

    async def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT task_id, state, error, progress, context FROM tasks WHERE task_id = $1", task_id)
            if not row:
                return None
            return {
                "task_id": row["task_id"],
                "state": row["state"],
                "error": row["error"],
                "progress": row["progress"] or {},
                "context": row["context"] or {},
            }

    async def get_task_context(self, task_id: str) -> Dict[str, Any]:
        state = await self.get_task_state(task_id)
        return state.get("context", {}) if state else {}

    async def update_task_context(self, task_id: str, context: Dict[str, Any]):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE tasks SET context = $1, updated_at = CURRENT_TIMESTAMP WHERE task_id = $2", json.dumps(context), task_id)

    async def get_state_transitions(self, task_id: str) -> list:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT from_state, to_state, reason, timestamp FROM state_transitions WHERE task_id = $1 ORDER BY timestamp ASC", task_id)
            return [
                {"from_state": r["from_state"], "to_state": r["to_state"], "reason": r["reason"], "timestamp": r["timestamp"].isoformat()}
                for r in rows
            ]


