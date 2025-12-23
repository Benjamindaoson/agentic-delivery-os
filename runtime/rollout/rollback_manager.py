"""
Rollback Manager: 自动回滚管理器
当 KPI 指标跌破阈值时自动回滚到上一个稳定版本
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime


class RollbackManager:
    """
    Rollback Manager：自动回滚管理器。
    
    当以下条件满足时触发回滚：
    - candidate failure_rate > max_failure_rate
    - candidate success_rate 显著低于 active
    - candidate avg_cost 显著高于 active
    """
    
    def __init__(
        self,
        state_path: str = "artifacts/rollouts/rollout_state.json",
        audit_log_path: str = "artifacts/rollouts/audit_log.jsonl"
    ):
        """
        初始化 Rollback Manager。
        
        Args:
            state_path: rollout 状态文件路径
            audit_log_path: 审计日志文件路径
        """
        self.state_path = state_path
        self.audit_log_path = audit_log_path
    
    def should_rollback(
        self,
        kpis: Dict[str, Any],
        thresholds: Dict[str, Any],
        active: str,
        candidate: str
    ) -> bool:
        """
        判断是否需要回滚。
        
        Args:
            kpis: KPI 数据，格式 {policy_id: {success_rate, avg_cost, failure_rate, ...}}
            thresholds: 阈值配置 {max_failure_rate, max_cost_increase, ...}
            active: active policy ID
            candidate: candidate policy ID
            
        Returns:
            bool: True 表示需要回滚
        """
        active_kpis = kpis.get(active, {})
        candidate_kpis = kpis.get(candidate, {})
        
        if not candidate_kpis:
            # 没有 candidate 的 KPI 数据，不回滚
            return False
        
        # 检查 1: failure_rate 超过阈值
        max_failure_rate = thresholds.get("max_failure_rate", 0.15)
        candidate_failure_rate = candidate_kpis.get("failure_rate", 0.0)
        
        if candidate_failure_rate > max_failure_rate:
            return True
        
        # 检查 2: success_rate 显著下降（相对于 active）
        min_success_uplift = thresholds.get("min_success_uplift", 0.0)
        active_success_rate = active_kpis.get("success_rate", 0.0)
        candidate_success_rate = candidate_kpis.get("success_rate", 0.0)
        
        if active_success_rate > 0:
            success_drop = active_success_rate - candidate_success_rate
            # 如果下降超过 5%，触发回滚
            if success_drop > 0.05:
                return True
        
        # 检查 3: cost 显著增加
        max_cost_increase = thresholds.get("max_cost_increase", 0.05)
        active_cost = active_kpis.get("avg_cost", 0.0)
        candidate_cost = candidate_kpis.get("avg_cost", 0.0)
        
        if active_cost > 0:
            cost_increase = (candidate_cost - active_cost) / active_cost
            if cost_increase > max_cost_increase:
                return True
        
        return False
    
    def rollback(self) -> Dict[str, Any]:
        """
        执行回滚：立即把 traffic_split 置回 100% active，stage=rollback。
        
        Returns:
            dict: 回滚结果
        """
        # 加载当前状态
        state = self._load_state()
        
        if not state:
            return {
                "success": False,
                "reason": "no_rollout_state",
                "timestamp": datetime.now().isoformat()
            }
        
        active_policy = state.get("active_policy")
        candidate_policy = state.get("candidate_policy")
        previous_stage = state.get("stage")
        previous_split = state.get("traffic_split", {})
        
        if not active_policy:
            return {
                "success": False,
                "reason": "no_active_policy",
                "timestamp": datetime.now().isoformat()
            }
        
        # 执行回滚
        new_state = {
            "active_policy": active_policy,
            "candidate_policy": candidate_policy,
            "stage": "rollback",
            "traffic_split": {active_policy: 1.0},
            "started_at": state.get("started_at"),
            "last_checked_at": datetime.now().isoformat(),
            "rollback_at": datetime.now().isoformat(),
            "rollback_from_stage": previous_stage,
            "rollback_from_split": previous_split,
            "kpi_window": state.get("kpi_window", {}),
            "thresholds": state.get("thresholds", {})
        }
        
        self._save_state(new_state)
        
        # 记录审计日志
        audit_entry = {
            "action": "rollback",
            "active_policy": active_policy,
            "candidate_policy": candidate_policy,
            "from_stage": previous_stage,
            "from_split": previous_split,
            "timestamp": datetime.now().isoformat()
        }
        self._append_audit_log(audit_entry)
        
        return {
            "success": True,
            "action": "rollback",
            "active_policy": active_policy,
            "candidate_policy": candidate_policy,
            "from_stage": previous_stage,
            "timestamp": datetime.now().isoformat()
        }
    
    def _load_state(self) -> Optional[Dict[str, Any]]:
        """加载 rollout 状态"""
        if not os.path.exists(self.state_path):
            return None
        
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _save_state(self, state: Dict[str, Any]) -> None:
        """保存 rollout 状态"""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _append_audit_log(self, entry: Dict[str, Any]) -> None:
        """追加审计日志"""
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
        
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")



