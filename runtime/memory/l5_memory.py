import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime

class LongTermMemory:
    def __init__(self, db_path: str = "memory/long_term/memory.db", vector_dim: int = 384):
        self.db_path = db_path
        self.vector_dim = vector_dim
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT,
                content TEXT,
                task_type TEXT,
                outcome TEXT,
                run_id TEXT,
                tags TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def store(self, key: str, content: Any, task_type: str, outcome: str, run_id: str, tags: List[str] = []):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO long_term_memory (key, content, task_type, outcome, run_id, tags)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (key, json.dumps(content), task_type, outcome, run_id, ",".join(tags)))
        conn.commit()
        conn.close()

    def query_by_type(self, task_type: str, outcome: str = "success") -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT key, content, outcome, run_id, timestamp 
            FROM long_term_memory 
            WHERE task_type = ? AND outcome = ?
            ORDER BY timestamp DESC
        ''', (task_type, outcome))
        rows = cursor.fetchall()
        conn.close()
        return [{"key": r[0], "content": json.loads(r[1]), "outcome": r[2], "run_id": r[3], "timestamp": r[4]} for r in rows]

class GlobalState:
    def __init__(self, state_path: str = "memory/global_state.json"):
        self.state_path = state_path
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, "r") as f:
                self.data = json.load(f)
                # Schema normalization for existing artifacts
                if "metrics" in self.data:
                    self.metrics = self.data["metrics"]
                else:
                    self.metrics = self.data
        else:
            self.metrics = {
                "total_runs": 0,
                "total_cost": 0.0,
                "successful_runs": 0,
                "failed_runs": 0,
                "avg_success_rate": 0.0,
                "last_updated": datetime.now().isoformat()
            }
            self.data = {"metrics": self.metrics, "system_version": "L5.0"}
            self.save()

    def update_stats(self, run_cost: float, tools_used: List[str], success: bool = True):
        self.metrics["total_runs"] = self.metrics.get("total_runs", 0) + 1
        self.metrics["total_cost"] = self.metrics.get("total_cost", 0.0) + run_cost
        
        if success:
            self.metrics["successful_runs"] = self.metrics.get("successful_runs", 0) + 1
        else:
            self.metrics["failed_runs"] = self.metrics.get("failed_runs", 0) + 1
            
        self.metrics["avg_success_rate"] = self.metrics["successful_runs"] / self.metrics["total_runs"]
        self.metrics["last_updated"] = datetime.now().isoformat()
        
        # Handle tool usage if it exists in the schema or add it
        if "tool_usage_stats" not in self.data:
            self.data["tool_usage_stats"] = {}
        
        for tool in tools_used:
            self.data["tool_usage_stats"][tool] = self.data["tool_usage_stats"].get(tool, 0) + 1
            
        self.save()

    def save(self):
        # Keep the data structure consistent
        if "metrics" not in self.data:
            self.data["metrics"] = self.metrics
        
        with open(self.state_path, "w") as f:
            json.dump(self.data, f, indent=2)
