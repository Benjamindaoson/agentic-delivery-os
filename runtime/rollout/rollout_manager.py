"""
Rollout Manager: 灰度发布状态机
管理 canary -> partial -> full 的发布流程
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from runtime.rollout.rollback_manager import RollbackManager


class RolloutManager:
    """
    Rollout Manager：灰度发布状态机。
    
    阶段规则：
    - canary: 5%
    - partial: 25%
    - full: 100%（candidate 成为 active，旧 active 保留为 previous）
    
    每次 advance 前必须检查 KPI Gate。
    """
    
    # 阶段定义
    STAGES = {
        "idle": 0,
        "canary": 1,
        "partial": 2,
        "full": 3,
        "rollback": -1
    }
    
    STAGE_TRAFFIC = {
        "canary": 0.05,
        "partial": 0.25,
        "full": 1.0
    }
    
    def __init__(
        self,
        trace_store,
        kpi_collector,
        rollback_manager: Optional[RollbackManager] = None,
        state_path: str = "artifacts/rollouts/rollout_state.json",
        audit_log_path: str = "artifacts/rollouts/audit_log.jsonl"
    ):
        """
        初始化 Rollout Manager。
        
        Args:
            trace_store: TraceStore 实例
            kpi_collector: PolicyKPICollector 实例
            rollback_manager: RollbackManager 实例（可选，会自动创建）
            state_path: rollout 状态文件路径
            audit_log_path: 审计日志文件路径
        """
        self.trace_store = trace_store
        self.kpi_collector = kpi_collector
        self.rollback_manager = rollback_manager or RollbackManager(state_path, audit_log_path)
        self.state_path = state_path
        self.audit_log_path = audit_log_path
    
    def start_canary(
        self,
        active: str,
        candidate: str,
        canary_pct: float = 0.05
    ) -> Dict[str, Any]:
        """
        启动 canary 阶段。
        
        Args:
            active: 当前 active policy ID
            candidate: 候选 policy ID
            canary_pct: canary 流量比例（默认 5%）
            
        Returns:
            dict: 启动结果
        """
        # 检查是否已有 rollout 在进行
        current_state = self.load_state()
        if current_state and current_state.get("stage") not in ["idle", "rollback", "full"]:
            return {
                "success": False,
                "reason": "rollout_in_progress",
                "current_stage": current_state.get("stage"),
                "timestamp": datetime.now().isoformat()
            }
        
        # 创建新的 rollout 状态
        new_state = {
            "active_policy": active,
            "candidate_policy": candidate,
            "stage": "canary",
            "traffic_split": {
                active: 1.0 - canary_pct,
                candidate: canary_pct
            },
            "started_at": datetime.now().isoformat(),
            "last_checked_at": datetime.now().isoformat(),
            "kpi_window": {
                "n_runs": 200,
                "lookback_minutes": 60
            },
            "thresholds": {
                "min_success_uplift": 0.00,
                "max_cost_increase": 0.05,
                "max_failure_rate": 0.15
            }
        }
        
        self.save_state(new_state)
        
        # 记录审计日志
        self._append_audit_log({
            "action": "start_canary",
            "active_policy": active,
            "candidate_policy": candidate,
            "canary_pct": canary_pct,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "action": "start_canary",
            "active_policy": active,
            "candidate_policy": candidate,
            "stage": "canary",
            "traffic_split": new_state["traffic_split"],
            "timestamp": datetime.now().isoformat()
        }
    
    def advance_stage(self) -> Dict[str, Any]:
        """
        推进 rollout 阶段：canary -> partial -> full。
        
        每次 advance 前必须检查 KPI Gate。
        
        Returns:
            dict: 推进结果
        """
        current_state = self.load_state()
        
        if not current_state:
            return {
                "success": False,
                "reason": "no_rollout_state",
                "timestamp": datetime.now().isoformat()
            }
        
        current_stage = current_state.get("stage", "idle")
        active_policy = current_state.get("active_policy")
        candidate_policy = current_state.get("candidate_policy")
        thresholds = current_state.get("thresholds", {})
        kpi_window = current_state.get("kpi_window", {})
        
        if current_stage == "idle":
            return {
                "success": False,
                "reason": "no_rollout_in_progress",
                "timestamp": datetime.now().isoformat()
            }
        
        if current_stage == "rollback":
            return {
                "success": False,
                "reason": "rollout_rolled_back",
                "timestamp": datetime.now().isoformat()
            }
        
        if current_stage == "full":
            return {
                "success": False,
                "reason": "already_full",
                "timestamp": datetime.now().isoformat()
            }
        
        # 检查 KPI Gate
        kpi_check = self._check_kpi_gate(
            active_policy, candidate_policy, thresholds, kpi_window
        )
        
        if not kpi_check["gate_pass"]:
            # KPI 不达标，触发回滚
            rollback_result = self.rollback_manager.rollback()
            return {
                "success": False,
                "reason": "kpi_gate_failed",
                "kpi_check": kpi_check,
                "rollback_triggered": True,
                "rollback_result": rollback_result,
                "timestamp": datetime.now().isoformat()
            }
        
        # 确定下一阶段
        next_stage = self._get_next_stage(current_stage)
        
        if not next_stage:
            return {
                "success": False,
                "reason": "invalid_stage_transition",
                "current_stage": current_stage,
                "timestamp": datetime.now().isoformat()
            }
        
        # 计算新的 traffic_split
        candidate_ratio = self.STAGE_TRAFFIC.get(next_stage, 0.0)
        
        if next_stage == "full":
            # 全量发布：candidate 成为新的 active
            new_state = {
                "active_policy": candidate_policy,
                "previous_policy": active_policy,
                "candidate_policy": None,
                "stage": "full",
                "traffic_split": {candidate_policy: 1.0},
                "started_at": current_state.get("started_at"),
                "completed_at": datetime.now().isoformat(),
                "last_checked_at": datetime.now().isoformat(),
                "kpi_window": kpi_window,
                "thresholds": thresholds
            }
        else:
            new_state = {
                "active_policy": active_policy,
                "candidate_policy": candidate_policy,
                "stage": next_stage,
                "traffic_split": {
                    active_policy: 1.0 - candidate_ratio,
                    candidate_policy: candidate_ratio
                },
                "started_at": current_state.get("started_at"),
                "last_checked_at": datetime.now().isoformat(),
                "kpi_window": kpi_window,
                "thresholds": thresholds
            }
        
        self.save_state(new_state)
        
        # 记录审计日志
        self._append_audit_log({
            "action": "advance_stage",
            "from_stage": current_stage,
            "to_stage": next_stage,
            "active_policy": new_state.get("active_policy"),
            "candidate_policy": new_state.get("candidate_policy"),
            "traffic_split": new_state.get("traffic_split"),
            "kpi_check": kpi_check,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "action": "advance_stage",
            "from_stage": current_stage,
            "to_stage": next_stage,
            "active_policy": new_state.get("active_policy"),
            "candidate_policy": new_state.get("candidate_policy"),
            "traffic_split": new_state.get("traffic_split"),
            "kpi_check": kpi_check,
            "timestamp": datetime.now().isoformat()
        }
    
    def check_and_maybe_advance_or_rollback(self) -> Dict[str, Any]:
        """
        检查当前 rollout 状态，根据 KPI 决定是推进还是回滚。
        
        这是 L5 Pipeline 的主要入口点。
        
        Returns:
            dict: 检查结果
        """
        current_state = self.load_state()
        
        if not current_state:
            return {
                "action": "none",
                "reason": "no_rollout_state",
                "timestamp": datetime.now().isoformat()
            }
        
        current_stage = current_state.get("stage", "idle")
        
        if current_stage in ["idle", "full"]:
            return {
                "action": "none",
                "reason": f"stage_is_{current_stage}",
                "timestamp": datetime.now().isoformat()
            }
        
        if current_stage == "rollback":
            return {
                "action": "none",
                "reason": "already_rolled_back",
                "timestamp": datetime.now().isoformat()
            }
        
        active_policy = current_state.get("active_policy")
        candidate_policy = current_state.get("candidate_policy")
        thresholds = current_state.get("thresholds", {})
        kpi_window = current_state.get("kpi_window", {})
        
        # 收集 KPI
        kpis = self.kpi_collector.collect(
            lookback_minutes=kpi_window.get("lookback_minutes", 60),
            min_runs=kpi_window.get("n_runs", 200)
        )
        
        # 检查是否需要回滚
        if self.rollback_manager.should_rollback(kpis, thresholds, active_policy, candidate_policy):
            rollback_result = self.rollback_manager.rollback()
            return {
                "action": "rollback",
                "reason": "kpi_degradation",
                "kpis": kpis,
                "rollback_result": rollback_result,
                "timestamp": datetime.now().isoformat()
            }
        
        # 如果 KPI 良好，考虑推进
        # 这里使用简化的逻辑：如果 candidate 的 KPI 满足要求，推进到下一阶段
        kpi_check = self._check_kpi_gate(active_policy, candidate_policy, thresholds, kpi_window)
        
        if kpi_check["gate_pass"]:
            # 可以推进
            return self.advance_stage()
        else:
            # KPI 未达标，但未触发回滚，保持当前阶段
            return {
                "action": "hold",
                "reason": "kpi_gate_not_passed",
                "kpi_check": kpi_check,
                "current_stage": current_stage,
                "timestamp": datetime.now().isoformat()
            }
    
    def load_state(self) -> Optional[Dict[str, Any]]:
        """加载 rollout 状态"""
        if not os.path.exists(self.state_path):
            return None
        
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def save_state(self, state: Dict[str, Any]) -> None:
        """保存 rollout 状态"""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def reset_to_idle(self) -> Dict[str, Any]:
        """重置为 idle 状态（用于测试或手动重置）"""
        from runtime.agent_registry.version_resolver import resolve_active_policy
        
        try:
            active_policy = resolve_active_policy().get("policy_version", "v1")
        except Exception:
            active_policy = "v1"
        
        new_state = {
            "active_policy": active_policy,
            "candidate_policy": None,
            "stage": "idle",
            "traffic_split": {active_policy: 1.0},
            "last_checked_at": datetime.now().isoformat()
        }
        
        self.save_state(new_state)
        
        self._append_audit_log({
            "action": "reset_to_idle",
            "active_policy": active_policy,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "action": "reset_to_idle",
            "state": new_state,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_next_stage(self, current_stage: str) -> Optional[str]:
        """获取下一阶段"""
        stage_order = ["canary", "partial", "full"]
        try:
            current_idx = stage_order.index(current_stage)
            if current_idx + 1 < len(stage_order):
                return stage_order[current_idx + 1]
            return None
        except ValueError:
            return None
    
    def _check_kpi_gate(
        self,
        active_policy: str,
        candidate_policy: str,
        thresholds: Dict[str, Any],
        kpi_window: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查 KPI 门禁"""
        # 收集 KPI
        kpis = self.kpi_collector.collect(
            lookback_minutes=kpi_window.get("lookback_minutes", 60),
            min_runs=kpi_window.get("n_runs", 200)
        )
        
        active_kpis = kpis.get(active_policy, {})
        candidate_kpis = kpis.get(candidate_policy, {})
        
        if not candidate_kpis:
            return {
                "gate_pass": False,
                "reason": "no_candidate_kpis",
                "kpis": kpis
            }
        
        # 检查条件
        checks = {}
        reasons = []
        blocked_reasons = []
        
        # 1. failure_rate
        max_failure_rate = thresholds.get("max_failure_rate", 0.15)
        candidate_failure_rate = candidate_kpis.get("failure_rate", 0.0)
        checks["failure_rate"] = candidate_failure_rate <= max_failure_rate
        if not checks["failure_rate"]:
            blocked_reasons.append(f"failure_rate {candidate_failure_rate:.2%} > {max_failure_rate:.2%}")
        
        # 2. success_rate（不低于 active）
        active_success_rate = active_kpis.get("success_rate", 0.0)
        candidate_success_rate = candidate_kpis.get("success_rate", 0.0)
        min_success_uplift = thresholds.get("min_success_uplift", 0.0)
        success_diff = candidate_success_rate - active_success_rate
        checks["success_rate"] = success_diff >= min_success_uplift
        if not checks["success_rate"]:
            blocked_reasons.append(f"success_rate diff {success_diff:.2%} < {min_success_uplift:.2%}")
        else:
            reasons.append(f"success_rate diff {success_diff:.2%}")
        
        # 3. avg_cost
        max_cost_increase = thresholds.get("max_cost_increase", 0.05)
        active_cost = active_kpis.get("avg_cost", 0.0)
        candidate_cost = candidate_kpis.get("avg_cost", 0.0)
        if active_cost > 0:
            cost_increase = (candidate_cost - active_cost) / active_cost
        else:
            cost_increase = 0.0
        checks["avg_cost"] = cost_increase <= max_cost_increase
        if not checks["avg_cost"]:
            blocked_reasons.append(f"cost_increase {cost_increase:.2%} > {max_cost_increase:.2%}")
        
        gate_pass = all(checks.values())
        
        return {
            "gate_pass": gate_pass,
            "checks": checks,
            "reasons": reasons,
            "blocked_reasons": blocked_reasons,
            "kpis": kpis
        }
    
    def _append_audit_log(self, entry: Dict[str, Any]) -> None:
        """追加审计日志"""
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
        
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")



