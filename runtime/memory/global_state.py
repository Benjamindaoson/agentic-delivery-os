"""
Global State Store: System-level statistics and state across sessions.
Provides cross-session aggregation and system health metrics.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    total_runs: int = 0
    total_sessions: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    
    # Success metrics
    successful_runs: int = 0
    failed_runs: int = 0
    
    # Performance
    avg_latency_ms: float = 0.0
    avg_quality_score: float = 0.0
    
    # Resource usage
    peak_memory_mb: float = 0.0
    peak_cpu_percent: float = 0.0
    
    # Time tracking
    first_run_at: str = ""
    last_run_at: str = ""
    total_runtime_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        return self.successful_runs / self.total_runs if self.total_runs > 0 else 0.0


@dataclass
class PolicyMetrics:
    """Metrics for a policy across runs."""
    policy_id: str
    policy_type: str  # retrieval, prompt, tool, agent
    
    # Usage
    total_uses: int = 0
    successful_uses: int = 0
    
    # Performance
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    
    # Trends
    recent_success_rate: float = 0.0  # Last 100 runs
    trend_direction: str = "stable"  # improving, stable, declining
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        return self.successful_uses / self.total_uses if self.total_uses > 0 else 0.0


@dataclass
class DailyStats:
    """Daily statistics."""
    date: str
    runs: int = 0
    successes: int = 0
    failures: int = 0
    cost: float = 0.0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalStateStore:
    """
    Global state store for system-wide statistics.
    
    Features:
    - Cross-session metrics
    - Policy performance tracking
    - Daily/weekly/monthly aggregation
    - Health monitoring
    """
    
    def __init__(self, storage_path: str = "memory/global_state.json"):
        self.storage_path = storage_path
        self.storage_dir = os.path.dirname(storage_path) or "."
        os.makedirs(self.storage_dir, exist_ok=True)
        
        self._system_metrics = SystemMetrics()
        self._policy_metrics: Dict[str, PolicyMetrics] = {}
        self._daily_stats: Dict[str, DailyStats] = {}
        self._config: Dict[str, Any] = {}
        
        self._load()
    
    def record_run(
        self,
        run_id: str,
        success: bool,
        cost: float,
        latency_ms: float,
        quality_score: float,
        policies_used: Optional[List[str]] = None
    ) -> None:
        """Record a run in global state."""
        now = datetime.now()
        
        # Update system metrics
        self._system_metrics.total_runs += 1
        if success:
            self._system_metrics.successful_runs += 1
        else:
            self._system_metrics.failed_runs += 1
        
        self._system_metrics.total_cost += cost
        
        # Running averages
        n = self._system_metrics.total_runs
        self._system_metrics.avg_latency_ms = (
            (self._system_metrics.avg_latency_ms * (n - 1) + latency_ms) / n
        )
        self._system_metrics.avg_quality_score = (
            (self._system_metrics.avg_quality_score * (n - 1) + quality_score) / n
        )
        
        if not self._system_metrics.first_run_at:
            self._system_metrics.first_run_at = now.isoformat()
        self._system_metrics.last_run_at = now.isoformat()
        
        # Update daily stats
        date_str = now.strftime("%Y-%m-%d")
        if date_str not in self._daily_stats:
            self._daily_stats[date_str] = DailyStats(date=date_str)
        
        daily = self._daily_stats[date_str]
        daily.runs += 1
        if success:
            daily.successes += 1
        else:
            daily.failures += 1
        daily.cost += cost
        daily.avg_latency_ms = (
            (daily.avg_latency_ms * (daily.runs - 1) + latency_ms) / daily.runs
        )
        daily.avg_quality = (
            (daily.avg_quality * (daily.runs - 1) + quality_score) / daily.runs
        )
        
        # Update policy metrics
        if policies_used:
            for policy_id in policies_used:
                self._update_policy_metrics(
                    policy_id, success, cost, latency_ms, quality_score
                )
        
        self._save()
    
    def record_session(self, session_id: str) -> None:
        """Record a new session."""
        self._system_metrics.total_sessions += 1
        self._save()
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get system-wide metrics."""
        return self._system_metrics
    
    def get_policy_metrics(self, policy_id: str) -> Optional[PolicyMetrics]:
        """Get metrics for a specific policy."""
        return self._policy_metrics.get(policy_id)
    
    def get_all_policy_metrics(self) -> List[PolicyMetrics]:
        """Get all policy metrics."""
        return list(self._policy_metrics.values())
    
    def get_daily_stats(self, days: int = 7) -> List[DailyStats]:
        """Get daily stats for last N days."""
        today = datetime.now()
        result = []
        
        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if date_str in self._daily_stats:
                result.append(self._daily_stats[date_str])
        
        return result
    
    def get_trend(self, metric: str = "success_rate", window_days: int = 7) -> str:
        """Calculate trend for a metric."""
        daily = self.get_daily_stats(window_days * 2)
        
        if len(daily) < 2:
            return "stable"
        
        # Split into recent and older
        half = len(daily) // 2
        recent = daily[:half]
        older = daily[half:]
        
        def avg_metric(stats: List[DailyStats]) -> float:
            if not stats:
                return 0.0
            if metric == "success_rate":
                total = sum(s.successes for s in stats)
                runs = sum(s.runs for s in stats)
                return total / runs if runs > 0 else 0.0
            elif metric == "quality":
                return sum(s.avg_quality for s in stats) / len(stats)
            elif metric == "cost":
                return sum(s.cost for s in stats) / len(stats)
            return 0.0
        
        recent_avg = avg_metric(recent)
        older_avg = avg_metric(older)
        
        if recent_avg > older_avg * 1.05:
            return "improving"
        elif recent_avg < older_avg * 0.95:
            return "declining"
        return "stable"
    
    def set_config(self, key: str, value: Any) -> None:
        """Set a global config value."""
        self._config[key] = value
        self._save()
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a global config value."""
        return self._config.get(key, default)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        metrics = self._system_metrics
        trend = self.get_trend("success_rate")
        
        # Determine health
        if metrics.success_rate >= 0.9 and trend in ["stable", "improving"]:
            health = "healthy"
        elif metrics.success_rate >= 0.7:
            health = "degraded"
        else:
            health = "unhealthy"
        
        return {
            "status": health,
            "success_rate": round(metrics.success_rate, 3),
            "trend": trend,
            "total_runs": metrics.total_runs,
            "total_cost": round(metrics.total_cost, 2),
            "avg_latency_ms": round(metrics.avg_latency_ms, 0),
            "avg_quality": round(metrics.avg_quality_score, 3),
            "last_run_at": metrics.last_run_at
        }
    
    def _update_policy_metrics(
        self,
        policy_id: str,
        success: bool,
        cost: float,
        latency_ms: float,
        quality: float
    ) -> None:
        """Update metrics for a policy."""
        if policy_id not in self._policy_metrics:
            # Infer policy type from ID
            policy_type = "unknown"
            if "retrieval" in policy_id.lower():
                policy_type = "retrieval"
            elif "prompt" in policy_id.lower():
                policy_type = "prompt"
            elif "tool" in policy_id.lower():
                policy_type = "tool"
            
            self._policy_metrics[policy_id] = PolicyMetrics(
                policy_id=policy_id,
                policy_type=policy_type
            )
        
        pm = self._policy_metrics[policy_id]
        pm.total_uses += 1
        if success:
            pm.successful_uses += 1
        
        n = pm.total_uses
        pm.avg_cost = (pm.avg_cost * (n - 1) + cost) / n
        pm.avg_latency_ms = (pm.avg_latency_ms * (n - 1) + latency_ms) / n
        pm.avg_quality = (pm.avg_quality * (n - 1) + quality) / n
        
        # Update recent success rate (simplified)
        pm.recent_success_rate = pm.success_rate
    
    def _save(self) -> None:
        """Save state to disk."""
        data = {
            "schema_version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "system_metrics": self._system_metrics.to_dict(),
            "policy_metrics": {
                k: v.to_dict() for k, v in self._policy_metrics.items()
            },
            "daily_stats": {
                k: v.to_dict() for k, v in self._daily_stats.items()
            },
            "config": self._config
        }
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load(self) -> None:
        """Load state from disk."""
        if not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            sm = data.get("system_metrics", {})
            self._system_metrics = SystemMetrics(**sm)
            
            for k, v in data.get("policy_metrics", {}).items():
                self._policy_metrics[k] = PolicyMetrics(**v)
            
            for k, v in data.get("daily_stats", {}).items():
                self._daily_stats[k] = DailyStats(**v)
            
            self._config = data.get("config", {})
        except (json.JSONDecodeError, IOError, TypeError):
            pass

