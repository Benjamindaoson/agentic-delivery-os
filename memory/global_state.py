"""
Global State Store: System-level statistics across all sessions.
Provides cross-session aggregates and trends.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
import sqlite3


@dataclass
class GlobalMetrics:
    """System-wide metrics."""
    total_runs: int = 0
    total_sessions: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    
    successful_runs: int = 0
    failed_runs: int = 0
    
    # Averages
    avg_success_rate: float = 0.0
    avg_cost_per_run: float = 0.0
    avg_latency_per_run: float = 0.0
    avg_quality_score: float = 0.0
    
    # By time period
    runs_today: int = 0
    runs_this_week: int = 0
    runs_this_month: int = 0
    
    # Updated timestamp
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyStats:
    """Statistics for a policy."""
    policy_id: str
    policy_type: str  # retrieval, prompt, planner, tool
    version: str
    
    total_uses: int = 0
    successful_uses: int = 0
    avg_quality: float = 0.0
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    
    is_active: bool = True
    promoted_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrendPoint:
    """A single point in a trend."""
    timestamp: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalStateStore:
    """
    Manages global system state and cross-session statistics.
    
    Provides:
    - System-wide metrics
    - Policy statistics
    - Trend tracking
    """
    
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        
        self.db_path = os.path.join(memory_dir, "global_state.db")
        self.state_path = os.path.join(memory_dir, "global_state.json")
        
        self._metrics = GlobalMetrics()
        self._policy_stats: Dict[str, PolicyStats] = {}
        self._trends: Dict[str, List[TrendPoint]] = {}
        
        self._init_db()
        self._load_state()
    
    def _init_db(self) -> None:
        """Initialize SQLite database for trends."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS run_history (
                run_id TEXT PRIMARY KEY,
                session_id TEXT,
                success INTEGER,
                cost REAL,
                latency_ms REAL,
                quality_score REAL,
                task_type TEXT,
                timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policy_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT,
                policy_type TEXT,
                run_id TEXT,
                success INTEGER,
                quality REAL,
                cost REAL,
                latency_ms REAL,
                timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trend_type TEXT,
                timestamp TEXT,
                value REAL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_timestamp ON run_history(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_id ON policy_usage(policy_id)
        """)
        
        conn.commit()
        conn.close()
    
    def record_run(
        self,
        run_id: str,
        session_id: str,
        success: bool,
        cost: float,
        latency_ms: float,
        quality_score: float,
        task_type: str
    ) -> None:
        """Record a run to global state."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO run_history
            (run_id, session_id, success, cost, latency_ms, quality_score, task_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, session_id, int(success), cost, latency_ms, quality_score, task_type, now))
        
        conn.commit()
        conn.close()
        
        # Update in-memory metrics
        self._update_metrics(success, cost, latency_ms, quality_score)
        self._save_state()
    
    def record_policy_usage(
        self,
        policy_id: str,
        policy_type: str,
        run_id: str,
        success: bool,
        quality: float,
        cost: float,
        latency_ms: float
    ) -> None:
        """Record policy usage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO policy_usage
            (policy_id, policy_type, run_id, success, quality, cost, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (policy_id, policy_type, run_id, int(success), quality, cost, latency_ms, now))
        
        conn.commit()
        conn.close()
        
        # Update policy stats
        self._update_policy_stats(policy_id, policy_type, success, quality, cost, latency_ms)
    
    def record_trend(
        self,
        trend_type: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a trend point."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO trends (trend_type, timestamp, value, metadata)
            VALUES (?, ?, ?, ?)
        """, (trend_type, now, value, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()
    
    def get_metrics(self) -> GlobalMetrics:
        """Get current global metrics."""
        return self._metrics
    
    def get_policy_stats(self, policy_id: str) -> Optional[PolicyStats]:
        """Get stats for a policy."""
        return self._policy_stats.get(policy_id)
    
    def get_all_policy_stats(self) -> Dict[str, PolicyStats]:
        """Get all policy stats."""
        return self._policy_stats
    
    def get_trend(
        self,
        trend_type: str,
        hours: int = 24
    ) -> List[TrendPoint]:
        """Get trend data for a period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute("""
            SELECT timestamp, value, metadata FROM trends
            WHERE trend_type = ? AND timestamp > ?
            ORDER BY timestamp ASC
        """, (trend_type, cutoff))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            TrendPoint(
                timestamp=row[0],
                value=row[1],
                metadata=json.loads(row[2]) if row[2] else {}
            )
            for row in rows
        ]
    
    def get_success_rate_trend(self, hours: int = 24) -> List[TrendPoint]:
        """Get success rate trend."""
        return self.get_trend("success_rate", hours)
    
    def get_cost_trend(self, hours: int = 24) -> List[TrendPoint]:
        """Get cost trend."""
        return self.get_trend("cost", hours)
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get daily summary."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(success) as successful,
                AVG(cost) as avg_cost,
                AVG(latency_ms) as avg_latency,
                AVG(quality_score) as avg_quality
            FROM run_history
            WHERE timestamp LIKE ?
        """, (f"{today}%",))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] > 0:
            return {
                "date": today,
                "total_runs": row[0],
                "successful_runs": row[1] or 0,
                "success_rate": (row[1] or 0) / row[0],
                "avg_cost": row[2] or 0,
                "avg_latency_ms": row[3] or 0,
                "avg_quality": row[4] or 0
            }
        
        return {"date": today, "total_runs": 0}
    
    def get_policy_comparison(self, policy_type: str) -> List[Dict[str, Any]]:
        """Compare policies of a type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                policy_id,
                COUNT(*) as uses,
                AVG(success) as success_rate,
                AVG(quality) as avg_quality,
                AVG(cost) as avg_cost
            FROM policy_usage
            WHERE policy_type = ?
            GROUP BY policy_id
            ORDER BY success_rate DESC
        """, (policy_type,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "policy_id": row[0],
                "uses": row[1],
                "success_rate": row[2],
                "avg_quality": row[3],
                "avg_cost": row[4]
            }
            for row in rows
        ]
    
    def export_state(self) -> Dict[str, Any]:
        """Export complete global state."""
        return {
            "exported_at": datetime.now().isoformat(),
            "metrics": self._metrics.to_dict(),
            "policy_stats": {
                pid: ps.to_dict() for pid, ps in self._policy_stats.items()
            },
            "daily_summary": self.get_daily_summary()
        }
    
    def _update_metrics(
        self,
        success: bool,
        cost: float,
        latency_ms: float,
        quality_score: float
    ) -> None:
        """Update in-memory metrics."""
        self._metrics.total_runs += 1
        self._metrics.total_cost += cost
        self._metrics.total_latency_ms += latency_ms
        
        if success:
            self._metrics.successful_runs += 1
        else:
            self._metrics.failed_runs += 1
        
        n = self._metrics.total_runs
        self._metrics.avg_success_rate = self._metrics.successful_runs / n
        self._metrics.avg_cost_per_run = self._metrics.total_cost / n
        self._metrics.avg_latency_per_run = self._metrics.total_latency_ms / n
        self._metrics.avg_quality_score = (
            self._metrics.avg_quality_score * (n - 1) + quality_score
        ) / n
        
        self._metrics.runs_today += 1
        self._metrics.last_updated = datetime.now().isoformat()
    
    def _update_policy_stats(
        self,
        policy_id: str,
        policy_type: str,
        success: bool,
        quality: float,
        cost: float,
        latency_ms: float
    ) -> None:
        """Update policy statistics."""
        if policy_id not in self._policy_stats:
            self._policy_stats[policy_id] = PolicyStats(
                policy_id=policy_id,
                policy_type=policy_type,
                version="1.0"
            )
        
        stats = self._policy_stats[policy_id]
        stats.total_uses += 1
        
        if success:
            stats.successful_uses += 1
        
        n = stats.total_uses
        stats.avg_quality = (stats.avg_quality * (n - 1) + quality) / n
        stats.avg_cost = (stats.avg_cost * (n - 1) + cost) / n
        stats.avg_latency_ms = (stats.avg_latency_ms * (n - 1) + latency_ms) / n
    
    def _save_state(self) -> None:
        """Save state to JSON file."""
        state = {
            "metrics": self._metrics.to_dict(),
            "policy_stats": {
                pid: ps.to_dict() for pid, ps in self._policy_stats.items()
            }
        }
        
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _load_state(self) -> None:
        """Load state from JSON file."""
        if not os.path.exists(self.state_path):
            return
        
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            if "metrics" in state:
                m = state["metrics"]
                self._metrics = GlobalMetrics(
                    total_runs=m.get("total_runs", 0),
                    total_sessions=m.get("total_sessions", 0),
                    total_cost=m.get("total_cost", 0.0),
                    total_latency_ms=m.get("total_latency_ms", 0.0),
                    successful_runs=m.get("successful_runs", 0),
                    failed_runs=m.get("failed_runs", 0),
                    avg_success_rate=m.get("avg_success_rate", 0.0),
                    avg_cost_per_run=m.get("avg_cost_per_run", 0.0),
                    avg_latency_per_run=m.get("avg_latency_per_run", 0.0),
                    avg_quality_score=m.get("avg_quality_score", 0.0),
                    runs_today=m.get("runs_today", 0),
                    last_updated=m.get("last_updated", "")
                )
            
            for pid, ps in state.get("policy_stats", {}).items():
                self._policy_stats[pid] = PolicyStats(
                    policy_id=ps["policy_id"],
                    policy_type=ps["policy_type"],
                    version=ps["version"],
                    total_uses=ps.get("total_uses", 0),
                    successful_uses=ps.get("successful_uses", 0),
                    avg_quality=ps.get("avg_quality", 0.0),
                    avg_cost=ps.get("avg_cost", 0.0),
                    avg_latency_ms=ps.get("avg_latency_ms", 0.0),
                    is_active=ps.get("is_active", True)
                )
        except (json.JSONDecodeError, IOError, KeyError):
            pass

