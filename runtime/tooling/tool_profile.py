"""
Tool Profile: Long-term tool performance tracking and governance.
Tracks usage stats, failures, ROI, risk profile across runs.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class ToolFailureRecord:
    """Record of a tool failure."""
    run_id: str
    failure_type: str
    error_message: str
    occurred_at: str
    recovery_action: str
    recovered: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolProfile:
    """Long-term profile for a tool."""
    tool_id: str
    tool_name: str
    
    # Usage stats
    total_invocations: int = 0
    successful_invocations: int = 0
    failed_invocations: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    
    # Derived metrics
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    
    # Failure tracking
    failure_rate: float = 0.0
    failure_types: Dict[str, int] = field(default_factory=dict)
    recent_failures: List[ToolFailureRecord] = field(default_factory=list)
    
    # ROI tracking
    value_contributed: float = 0.0  # Estimated value from successful uses
    roi_score: float = 0.0  # value / cost
    
    # Risk profile
    risk_tier: str = "low"  # low, medium, high, critical
    risk_score: float = 0.0
    has_side_effects: bool = False
    requires_sandbox: bool = False
    
    # Status
    enabled: bool = True
    degraded: bool = False
    degraded_reason: Optional[str] = None
    
    # Auto-governance
    auto_disable_threshold: float = 0.5  # Disable if failure_rate > threshold
    consecutive_failures: int = 0
    max_consecutive_failures: int = 5
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
    
    @property
    def success_rate(self) -> float:
        return self.successful_invocations / self.total_invocations if self.total_invocations > 0 else 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "total_invocations": self.total_invocations,
            "successful_invocations": self.successful_invocations,
            "failed_invocations": self.failed_invocations,
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "total_cost": round(self.total_cost, 4),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "avg_cost": round(self.avg_cost, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "failure_types": self.failure_types,
            "recent_failures": [f.to_dict() for f in self.recent_failures[-10:]],
            "value_contributed": round(self.value_contributed, 2),
            "roi_score": round(self.roi_score, 2),
            "risk_tier": self.risk_tier,
            "risk_score": round(self.risk_score, 4),
            "has_side_effects": self.has_side_effects,
            "requires_sandbox": self.requires_sandbox,
            "enabled": self.enabled,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version
        }
    
    def record_invocation(
        self,
        success: bool,
        cost: float,
        latency_ms: float,
        value_estimate: float = 0.0,
        failure_type: Optional[str] = None,
        run_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record a tool invocation."""
        self.total_invocations += 1
        self.total_cost += cost
        self.total_latency_ms += latency_ms
        
        if success:
            self.successful_invocations += 1
            self.value_contributed += value_estimate
            self.consecutive_failures = 0
        else:
            self.failed_invocations += 1
            self.consecutive_failures += 1
            
            if failure_type:
                self.failure_types[failure_type] = self.failure_types.get(failure_type, 0) + 1
                
                self.recent_failures.append(ToolFailureRecord(
                    run_id=run_id or "unknown",
                    failure_type=failure_type,
                    error_message=error_message or "",
                    occurred_at=datetime.now().isoformat(),
                    recovery_action="none",
                    recovered=False
                ))
        
        # Update derived metrics
        self.avg_cost = self.total_cost / self.total_invocations
        self.avg_latency_ms = self.total_latency_ms / self.total_invocations
        self.failure_rate = self.failed_invocations / self.total_invocations
        self.roi_score = self.value_contributed / self.total_cost if self.total_cost > 0 else 0
        
        # Auto-governance checks
        self._check_auto_governance()
        
        self.updated_at = datetime.now().isoformat()
    
    def _check_auto_governance(self) -> None:
        """Check if tool should be auto-degraded or disabled."""
        # Check consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.degraded = True
            self.degraded_reason = f"Consecutive failures: {self.consecutive_failures}"
        
        # Check failure rate (only after sufficient samples)
        if self.total_invocations >= 10 and self.failure_rate > self.auto_disable_threshold:
            self.enabled = False
            self.degraded = True
            self.degraded_reason = f"High failure rate: {self.failure_rate:.2%}"
    
    def reset_degraded_status(self) -> None:
        """Reset degraded status (manual intervention)."""
        self.degraded = False
        self.degraded_reason = None
        self.consecutive_failures = 0
        self.enabled = True
        self.updated_at = datetime.now().isoformat()


class ToolProfileManager:
    """
    Manages long-term tool profiles.
    
    Provides:
    - Cross-run usage tracking
    - Automatic degradation on failures
    - ROI and risk analysis
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.profiles_dir = os.path.join(artifacts_dir, "tool_profiles")
        self.failures_dir = os.path.join(artifacts_dir, "tool_failures")
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.failures_dir, exist_ok=True)
        
        self._profiles: Dict[str, ToolProfile] = {}
        self._load_profiles()
    
    def get_profile(self, tool_id: str, tool_name: Optional[str] = None) -> ToolProfile:
        """Get or create tool profile."""
        if tool_id not in self._profiles:
            self._profiles[tool_id] = ToolProfile(
                tool_id=tool_id,
                tool_name=tool_name or tool_id
            )
        return self._profiles[tool_id]
    
    def record_invocation(
        self,
        tool_id: str,
        run_id: str,
        success: bool,
        cost: float,
        latency_ms: float,
        value_estimate: float = 0.0,
        failure_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record a tool invocation."""
        profile = self.get_profile(tool_id)
        profile.record_invocation(
            success=success,
            cost=cost,
            latency_ms=latency_ms,
            value_estimate=value_estimate,
            failure_type=failure_type,
            run_id=run_id,
            error_message=error_message
        )
        self._save_profile(profile)
        
        # Save failure details separately
        if not success and failure_type:
            self._save_failure(run_id, tool_id, failure_type, error_message)
    
    def is_tool_available(self, tool_id: str) -> bool:
        """Check if tool is available for use."""
        profile = self.get_profile(tool_id)
        return profile.enabled and not profile.degraded
    
    def get_available_tools(self, tool_ids: List[str]) -> List[str]:
        """Filter to only available tools."""
        return [tid for tid in tool_ids if self.is_tool_available(tid)]
    
    def get_tool_risk_report(self) -> Dict[str, Any]:
        """Get risk report for all tools."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_tools": len(self._profiles),
            "high_risk_tools": [],
            "degraded_tools": [],
            "disabled_tools": [],
            "healthy_tools": []
        }
        
        for tool_id, profile in self._profiles.items():
            tool_info = {
                "tool_id": tool_id,
                "failure_rate": profile.failure_rate,
                "risk_tier": profile.risk_tier
            }
            
            if not profile.enabled:
                report["disabled_tools"].append(tool_info)
            elif profile.degraded:
                report["degraded_tools"].append(tool_info)
            elif profile.risk_tier in ["high", "critical"]:
                report["high_risk_tools"].append(tool_info)
            else:
                report["healthy_tools"].append(tool_info)
        
        return report
    
    def reset_tool(self, tool_id: str) -> bool:
        """Reset a degraded/disabled tool."""
        if tool_id in self._profiles:
            self._profiles[tool_id].reset_degraded_status()
            self._save_profile(self._profiles[tool_id])
            return True
        return False
    
    def export_all_profiles(self) -> Dict[str, Any]:
        """Export all profiles for analysis."""
        return {
            "exported_at": datetime.now().isoformat(),
            "total_tools": len(self._profiles),
            "profiles": {
                tid: p.to_dict() for tid, p in self._profiles.items()
            }
        }
    
    def _save_profile(self, profile: ToolProfile) -> None:
        """Save profile to artifact."""
        path = os.path.join(self.profiles_dir, f"{profile.tool_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_failure(
        self,
        run_id: str,
        tool_id: str,
        failure_type: str,
        error_message: Optional[str]
    ) -> None:
        """Save failure details."""
        path = os.path.join(self.failures_dir, f"{run_id}.json")
        
        # Load existing or create new
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"run_id": run_id, "failures": []}
        
        data["failures"].append({
            "tool_id": tool_id,
            "failure_type": failure_type,
            "error_message": error_message,
            "occurred_at": datetime.now().isoformat()
        })
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_profiles(self) -> None:
        """Load all profiles from artifacts."""
        if not os.path.exists(self.profiles_dir):
            return
        
        for filename in os.listdir(self.profiles_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.profiles_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    profile = self._dict_to_profile(data)
                    self._profiles[profile.tool_id] = profile
                except (json.JSONDecodeError, IOError, KeyError):
                    pass
    
    def _dict_to_profile(self, data: Dict[str, Any]) -> ToolProfile:
        """Convert dict to ToolProfile."""
        recent_failures = []
        for f in data.get("recent_failures", []):
            recent_failures.append(ToolFailureRecord(**f))
        
        return ToolProfile(
            tool_id=data["tool_id"],
            tool_name=data.get("tool_name", data["tool_id"]),
            total_invocations=data.get("total_invocations", 0),
            successful_invocations=data.get("successful_invocations", 0),
            failed_invocations=data.get("failed_invocations", 0),
            total_cost=data.get("total_cost", 0.0),
            total_latency_ms=data.get("total_latency_ms", 0.0),
            avg_cost=data.get("avg_cost", 0.0),
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            failure_rate=data.get("failure_rate", 0.0),
            failure_types=data.get("failure_types", {}),
            recent_failures=recent_failures,
            value_contributed=data.get("value_contributed", 0.0),
            roi_score=data.get("roi_score", 0.0),
            risk_tier=data.get("risk_tier", "low"),
            risk_score=data.get("risk_score", 0.0),
            has_side_effects=data.get("has_side_effects", False),
            requires_sandbox=data.get("requires_sandbox", False),
            enabled=data.get("enabled", True),
            degraded=data.get("degraded", False),
            degraded_reason=data.get("degraded_reason"),
            consecutive_failures=data.get("consecutive_failures", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



