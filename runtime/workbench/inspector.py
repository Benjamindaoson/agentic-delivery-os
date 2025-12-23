"""
Inspector: Minimal workbench views for system inspection.
Provides agent inspector, policy timeline, and trend views.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from runtime.agents.agent_profile import AgentProfileManager
from runtime.tooling.tool_profile import ToolProfileManager
from memory.global_state import GlobalStateStore


class AgentInspector:
    """
    Inspector for agent profiles and performance.
    
    Provides:
    - Agent overview
    - Performance breakdown
    - Failure analysis
    - Task affinity view
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.agent_manager = AgentProfileManager(artifacts_dir=artifacts_dir)
    
    def get_overview(self) -> Dict[str, Any]:
        """Get overview of all agents."""
        profiles = self.agent_manager.export_all_profiles()
        
        overview = {
            "generated_at": datetime.now().isoformat(),
            "total_agents": len(profiles.get("profiles", {})),
            "agents": []
        }
        
        for agent_id, profile in profiles.get("profiles", {}).items():
            overview["agents"].append({
                "agent_id": agent_id,
                "total_runs": profile.get("total_runs", 0),
                "success_rate": profile.get("success_rate", 0),
                "avg_quality": profile.get("avg_quality", 0),
                "avg_cost": profile.get("avg_cost", 0),
                "trend": profile.get("success_rate_trend", "stable")
            })
        
        # Sort by success rate
        overview["agents"].sort(key=lambda x: x["success_rate"], reverse=True)
        
        return overview
    
    def get_agent_detail(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed view for a specific agent."""
        profile = self.agent_manager.get_profile(agent_id)
        
        if profile.total_runs == 0:
            return None
        
        return {
            "agent_id": agent_id,
            "performance": {
                "total_runs": profile.total_runs,
                "success_rate": profile.success_rate,
                "avg_quality": profile.avg_quality,
                "avg_cost": profile.avg_cost,
                "avg_latency_ms": profile.avg_latency_ms
            },
            "failure_analysis": {
                "total_failures": profile.failed_runs,
                "failure_modes": {
                    mode_id: mode.count
                    for mode_id, mode in profile.failure_modes.items()
                }
            },
            "task_affinity": {
                task_type: {
                    "runs": aff.total_runs,
                    "success_rate": aff.success_rate,
                    "avg_quality": aff.avg_quality
                }
                for task_type, aff in profile.task_affinities.items()
            },
            "policy_version": profile.current_policy_version,
            "updated_at": profile.updated_at
        }
    
    def get_ranking(self) -> List[Dict[str, Any]]:
        """Get agent ranking by performance."""
        return self.agent_manager.get_agent_ranking()


class ToolInspector:
    """
    Inspector for tool profiles and health.
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.tool_manager = ToolProfileManager(artifacts_dir=artifacts_dir)
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Get tool risk report."""
        return self.tool_manager.get_tool_risk_report()
    
    def get_tool_detail(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed view for a specific tool."""
        profile = self.tool_manager.get_profile(tool_id)
        
        if profile.total_invocations == 0:
            return None
        
        return {
            "tool_id": tool_id,
            "tool_name": profile.tool_name,
            "health": {
                "enabled": profile.enabled,
                "degraded": profile.degraded,
                "degraded_reason": profile.degraded_reason
            },
            "usage": {
                "total_invocations": profile.total_invocations,
                "success_rate": profile.success_rate,
                "failure_rate": profile.failure_rate,
                "consecutive_failures": profile.consecutive_failures
            },
            "cost_analysis": {
                "total_cost": profile.total_cost,
                "avg_cost": profile.avg_cost,
                "value_contributed": profile.value_contributed,
                "roi_score": profile.roi_score
            },
            "latency": {
                "total_ms": profile.total_latency_ms,
                "avg_ms": profile.avg_latency_ms
            },
            "failure_types": profile.failure_types,
            "risk_tier": profile.risk_tier,
            "updated_at": profile.updated_at
        }


class PolicyTimeline:
    """
    Timeline view for policy versions and promotions.
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
    
    def get_policy_history(self, policy_type: str = "all") -> List[Dict[str, Any]]:
        """Get policy version history."""
        # Load from policy artifacts
        policy_dir = os.path.join(self.artifacts_dir, "policy", "candidates")
        history = []
        
        if os.path.exists(policy_dir):
            for filename in os.listdir(policy_dir):
                if filename.endswith(".json"):
                    path = os.path.join(policy_dir, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        if policy_type == "all" or data.get("type") == policy_type:
                            history.append({
                                "policy_id": data.get("candidate_id"),
                                "status": data.get("status"),
                                "created_at": data.get("created_at"),
                                "genome": data.get("genome", {})
                            })
                    except (json.JSONDecodeError, IOError):
                        pass
        
        # Sort by creation time
        history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return history
    
    def get_active_policies(self) -> Dict[str, Any]:
        """Get currently active policies."""
        registry_path = os.path.join(self.artifacts_dir, "policy", "registry.json")
        
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {"policies": []}


class TrendViewer:
    """
    Viewer for long-term trends.
    """
    
    def __init__(self, memory_dir: str = "memory"):
        self.global_state = GlobalStateStore(memory_dir=memory_dir)
    
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get daily summary."""
        return self.global_state.get_daily_summary()
    
    def get_success_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get success rate trend."""
        points = self.global_state.get_success_rate_trend(hours)
        return [p.to_dict() for p in points]
    
    def get_cost_trend(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get cost trend."""
        points = self.global_state.get_cost_trend(hours)
        return [p.to_dict() for p in points]
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        metrics = self.global_state.get_metrics()
        return metrics.to_dict()
    
    def get_policy_comparison(self, policy_type: str) -> List[Dict[str, Any]]:
        """Compare policies of a type."""
        return self.global_state.get_policy_comparison(policy_type)


class Workbench:
    """
    Main workbench for system inspection.
    
    Combines all inspectors and viewers.
    """
    
    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        memory_dir: str = "memory"
    ):
        self.agent_inspector = AgentInspector(artifacts_dir)
        self.tool_inspector = ToolInspector(artifacts_dir)
        self.policy_timeline = PolicyTimeline(artifacts_dir)
        self.trend_viewer = TrendViewer(memory_dir)
    
    def get_dashboard(self) -> Dict[str, Any]:
        """Get complete dashboard view."""
        return {
            "generated_at": datetime.now().isoformat(),
            "agents": self.agent_inspector.get_overview(),
            "tools": self.tool_inspector.get_risk_report(),
            "metrics": self.trend_viewer.get_metrics_summary(),
            "daily_summary": self.trend_viewer.get_daily_summary()
        }
    
    def export_full_state(self) -> Dict[str, Any]:
        """Export complete system state for analysis."""
        return {
            "exported_at": datetime.now().isoformat(),
            "agents": self.agent_inspector.get_overview(),
            "agent_ranking": self.agent_inspector.get_ranking(),
            "tools": self.tool_inspector.get_risk_report(),
            "metrics": self.trend_viewer.get_metrics_summary(),
            "daily_summary": self.trend_viewer.get_daily_summary(),
            "active_policies": self.policy_timeline.get_active_policies()
        }



