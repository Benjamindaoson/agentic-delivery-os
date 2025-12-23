"""
TenantBudgetController: 租户级预算控制器
支持租户级成本跟踪、预算执行、多任务并发成本控制
"""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum


class BudgetStatus(str, Enum):
    """预算状态"""
    HEALTHY = "healthy"  # 使用率 < 80%
    WARNING = "warning"  # 使用率 80-90%
    CRITICAL = "critical"  # 使用率 90-100%
    EXCEEDED = "exceeded"  # 使用率 > 100%


@dataclass
class TenantBudgetUsage:
    """租户预算使用情况"""
    tenant_id: str
    period: str  # daily/monthly
    period_start: str
    period_end: str
    budget_limit: float
    current_usage: float
    usage_rate: float  # 0.0-1.0+
    status: BudgetStatus
    concurrent_runs: int
    max_concurrent_runs: int
    cost_by_category: Dict[str, float]  # llm/retrieval/storage/etc
    top_cost_tasks: List[Dict[str, Any]]
    updated_at: str


class TenantBudgetController:
    """
    租户预算控制器
    
    Features:
    - 租户级成本跟踪
    - 并发任务成本累计
    - 预算超限自动阻断
    - 成本预测与告警
    - 租户级成本报表
    """
    
    def __init__(self, artifacts_dir: str = "artifacts/tenants"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # In-memory cache for fast access
        self._usage_cache: Dict[str, TenantBudgetUsage] = {}
        self._running_tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> task_info
    
    def register_task_start(
        self,
        tenant_id: str,
        task_id: str,
        run_id: str,
        estimated_cost: float = 0.0
    ) -> Dict[str, Any]:
        """
        注册任务开始，检查预算
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "budget_status": BudgetStatus,
                "budget_remaining": float
            }
        """
        # Load or initialize usage
        usage = self._get_usage(tenant_id)
        
        # Check budget
        projected_usage = usage.current_usage + estimated_cost
        would_exceed = projected_usage > usage.budget_limit
        
        # Check concurrent runs
        concurrent_exceeded = usage.concurrent_runs >= usage.max_concurrent_runs
        
        if would_exceed or concurrent_exceeded:
            return {
                "allowed": False,
                "reason": (
                    "Budget limit exceeded" if would_exceed
                    else f"Concurrent runs limit exceeded ({usage.max_concurrent_runs})"
                ),
                "budget_status": usage.status.value,
                "budget_remaining": max(0, usage.budget_limit - usage.current_usage),
                "concurrent_runs": usage.concurrent_runs,
                "max_concurrent_runs": usage.max_concurrent_runs
            }
        
        # Register task
        self._running_tasks[task_id] = {
            "tenant_id": tenant_id,
            "run_id": run_id,
            "started_at": datetime.now().isoformat(),
            "estimated_cost": estimated_cost,
            "actual_cost": 0.0
        }
        
        usage.concurrent_runs += 1
        self._save_usage(usage)
        
        return {
            "allowed": True,
            "reason": "Budget check passed",
            "budget_status": usage.status.value,
            "budget_remaining": max(0, usage.budget_limit - usage.current_usage),
            "concurrent_runs": usage.concurrent_runs,
            "max_concurrent_runs": usage.max_concurrent_runs
        }
    
    def record_task_cost(
        self,
        tenant_id: str,
        task_id: str,
        cost_delta: float,
        cost_category: str = "other"
    ):
        """记录任务成本增量"""
        usage = self._get_usage(tenant_id)
        
        # Update total usage
        usage.current_usage += cost_delta
        
        # Update category breakdown
        if cost_category not in usage.cost_by_category:
            usage.cost_by_category[cost_category] = 0.0
        usage.cost_by_category[cost_category] += cost_delta
        
        # Update task cost
        if task_id in self._running_tasks:
            self._running_tasks[task_id]["actual_cost"] += cost_delta
        
        # Recalculate status
        usage.usage_rate = usage.current_usage / usage.budget_limit if usage.budget_limit > 0 else 0.0
        usage.status = self._calculate_status(usage.usage_rate)
        usage.updated_at = datetime.now().isoformat()
        
        self._save_usage(usage)
    
    def register_task_end(
        self,
        tenant_id: str,
        task_id: str,
        final_cost: float
    ):
        """注册任务结束"""
        usage = self._get_usage(tenant_id)
        
        if task_id in self._running_tasks:
            task_info = self._running_tasks.pop(task_id)
            
            # Update top cost tasks
            usage.top_cost_tasks.append({
                "task_id": task_id,
                "run_id": task_info["run_id"],
                "cost": final_cost,
                "completed_at": datetime.now().isoformat()
            })
            
            # Keep only top 100
            usage.top_cost_tasks = sorted(
                usage.top_cost_tasks,
                key=lambda x: x["cost"],
                reverse=True
            )[:100]
        
        usage.concurrent_runs = max(0, usage.concurrent_runs - 1)
        usage.updated_at = datetime.now().isoformat()
        
        self._save_usage(usage)
    
    def get_budget_usage(self, tenant_id: str) -> TenantBudgetUsage:
        """获取租户预算使用情况"""
        return self._get_usage(tenant_id)
    
    def get_running_tasks(self, tenant_id: str) -> List[Dict[str, Any]]:
        """获取租户当前运行中的任务"""
        return [
            {**info, "task_id": task_id}
            for task_id, info in self._running_tasks.items()
            if info["tenant_id"] == tenant_id
        ]
    
    def reset_budget_period(self, tenant_id: str, new_limit: Optional[float] = None):
        """重置预算周期（如新的一天/月）"""
        usage = self._get_usage(tenant_id)
        
        # Archive old usage
        self._archive_usage(usage)
        
        # Reset
        if new_limit is not None:
            usage.budget_limit = new_limit
        
        usage.current_usage = 0.0
        usage.usage_rate = 0.0
        usage.status = BudgetStatus.HEALTHY
        usage.cost_by_category = {}
        usage.top_cost_tasks = []
        usage.period_start = datetime.now().isoformat()
        usage.period_end = (datetime.now() + timedelta(days=1)).isoformat()
        usage.updated_at = datetime.now().isoformat()
        
        self._save_usage(usage)
    
    def can_proceed_with_cost(
        self,
        tenant_id: str,
        estimated_additional_cost: float
    ) -> Dict[str, Any]:
        """
        检查是否可以继续（用于执行中的成本检查）
        
        Returns:
            {
                "can_proceed": bool,
                "action": "continue" | "degrade" | "terminate",
                "reason": str,
                "budget_remaining": float
            }
        """
        usage = self._get_usage(tenant_id)
        
        projected_usage = usage.current_usage + estimated_additional_cost
        projected_rate = projected_usage / usage.budget_limit if usage.budget_limit > 0 else 0.0
        
        budget_remaining = max(0, usage.budget_limit - projected_usage)
        
        if projected_rate >= 1.0:
            return {
                "can_proceed": False,
                "action": "terminate",
                "reason": f"Projected cost would exceed budget (projected: {projected_rate:.1%})",
                "budget_remaining": budget_remaining
            }
        elif projected_rate >= 0.9:
            return {
                "can_proceed": True,
                "action": "degrade",
                "reason": f"Approaching budget limit (projected: {projected_rate:.1%})",
                "budget_remaining": budget_remaining
            }
        else:
            return {
                "can_proceed": True,
                "action": "continue",
                "reason": f"Within budget (projected: {projected_rate:.1%})",
                "budget_remaining": budget_remaining
            }
    
    def generate_cost_report(self, tenant_id: str) -> Dict[str, Any]:
        """生成租户成本报表"""
        usage = self._get_usage(tenant_id)
        
        report = {
            "tenant_id": tenant_id,
            "period": usage.period,
            "period_range": {
                "start": usage.period_start,
                "end": usage.period_end
            },
            "budget": {
                "limit": usage.budget_limit,
                "used": usage.current_usage,
                "remaining": max(0, usage.budget_limit - usage.current_usage),
                "usage_rate": usage.usage_rate,
                "status": usage.status.value
            },
            "concurrency": {
                "current_runs": usage.concurrent_runs,
                "max_allowed": usage.max_concurrent_runs
            },
            "cost_breakdown": usage.cost_by_category,
            "top_cost_tasks": usage.top_cost_tasks[:10],
            "running_tasks": self.get_running_tasks(tenant_id),
            "generated_at": datetime.now().isoformat()
        }
        
        # Save report
        report_path = os.path.join(
            self.artifacts_dir,
            tenant_id,
            f"cost_report_{datetime.now().strftime('%Y%m%d')}.json"
        )
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report
    
    def _get_usage(self, tenant_id: str) -> TenantBudgetUsage:
        """获取或初始化租户使用情况"""
        if tenant_id in self._usage_cache:
            return self._usage_cache[tenant_id]
        
        # Try to load from disk
        usage_path = os.path.join(self.artifacts_dir, tenant_id, "budget_usage.json")
        if os.path.exists(usage_path):
            try:
                with open(usage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    usage = TenantBudgetUsage(**data)
                    # Convert status string to enum
                    usage.status = BudgetStatus(usage.status)
                    self._usage_cache[tenant_id] = usage
                    return usage
            except Exception:
                pass
        
        # Load tenant config to get budget limits
        tenant_config_path = os.path.join(self.artifacts_dir, f"{tenant_id}.json")
        budget_limit = 1000.0  # Default
        max_concurrent = 10  # Default
        
        if os.path.exists(tenant_config_path):
            try:
                with open(tenant_config_path, "r", encoding="utf-8") as f:
                    tenant_data = json.load(f)
                    budget_profile = tenant_data.get("budget_profile", {})
                    budget_limit = budget_profile.get("max_cost_per_day", 1000.0)
                    max_concurrent = budget_profile.get("max_concurrent_runs", 10)
            except Exception:
                pass
        
        # Initialize new usage
        usage = TenantBudgetUsage(
            tenant_id=tenant_id,
            period="daily",
            period_start=datetime.now().isoformat(),
            period_end=(datetime.now() + timedelta(days=1)).isoformat(),
            budget_limit=budget_limit,
            current_usage=0.0,
            usage_rate=0.0,
            status=BudgetStatus.HEALTHY,
            concurrent_runs=0,
            max_concurrent_runs=max_concurrent,
            cost_by_category={},
            top_cost_tasks=[],
            updated_at=datetime.now().isoformat()
        )
        
        self._usage_cache[tenant_id] = usage
        self._save_usage(usage)
        
        return usage
    
    def _save_usage(self, usage: TenantBudgetUsage):
        """保存使用情况"""
        usage_path = os.path.join(self.artifacts_dir, usage.tenant_id, "budget_usage.json")
        os.makedirs(os.path.dirname(usage_path), exist_ok=True)
        
        data = asdict(usage)
        data["status"] = usage.status.value  # Convert enum to string
        
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self._usage_cache[usage.tenant_id] = usage
    
    def _archive_usage(self, usage: TenantBudgetUsage):
        """归档旧的使用情况"""
        archive_path = os.path.join(
            self.artifacts_dir,
            usage.tenant_id,
            f"budget_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        
        data = asdict(usage)
        data["status"] = usage.status.value
        
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _calculate_status(self, usage_rate: float) -> BudgetStatus:
        """计算预算状态"""
        if usage_rate >= 1.0:
            return BudgetStatus.EXCEEDED
        elif usage_rate >= 0.9:
            return BudgetStatus.CRITICAL
        elif usage_rate >= 0.8:
            return BudgetStatus.WARNING
        else:
            return BudgetStatus.HEALTHY


# Global instance
_global_controller: Optional[TenantBudgetController] = None


def get_tenant_budget_controller() -> TenantBudgetController:
    """获取全局租户预算控制器"""
    global _global_controller
    if _global_controller is None:
        _global_controller = TenantBudgetController()
    return _global_controller

