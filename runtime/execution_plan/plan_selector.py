"""
Plan Selector: 计划选择器（规则驱动、非学习型、可静态审计）
基于 GovernanceDecision 和信号选择执行计划
"""
from typing import Dict, Any, Optional
from runtime.execution_plan.plan_registry import PlanRegistry
from runtime.execution_plan.plan_definition import ExecutionPlan, PlanPath
from runtime.governance.governance_engine import GovernanceDecision, ExecutionMode

class PlanSelector:
    """计划选择器：规则驱动、非学习型、可静态审计"""
    
    def __init__(self):
        self.registry = PlanRegistry()
    
    def select_plan(
        self,
        governance_decision: GovernanceDecision,
        signals: Dict[str, Any],
        last_evaluation_feedback: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        选择执行计划（规则驱动）
        
        规则（优先级从高到低）：
        1. 如果 governance_decision.execution_mode == PAUSED → 不选择计划（由调用方处理）
        2. 如果 governance_decision.execution_mode == MINIMAL → 选择 MINIMAL 计划
        3. 如果 governance_decision.execution_mode == DEGRADED → 选择 DEGRADED 计划
        4. 如果预算受限（budget_remaining < 100）→ 选择 DEGRADED 计划
        5. 如果 Evaluation 反馈上次失败且失败类型为数据问题 → 选择 DEGRADED 计划（跳过数据节点）
        6. 其他 → 选择 NORMAL 计划
        
        所有规则都是静态的、可审计的、非学习型的
        """
        execution_mode = governance_decision.execution_mode
        
        # 规则 1: PAUSED 模式不选择计划
        if execution_mode == ExecutionMode.PAUSED:
            # 返回一个空计划（由调用方处理暂停）
            return ExecutionPlan(
                plan_id="paused",
                plan_version="1.0",
                path_type=PlanPath.NORMAL,
                description="Execution paused, no plan selected"
            )
        
        # 规则 2: MINIMAL 模式
        if execution_mode == ExecutionMode.MINIMAL:
            return self.registry.get_plan("minimal_v1")
        
        # 规则 3: DEGRADED 模式
        if execution_mode == ExecutionMode.DEGRADED:
            return self.registry.get_plan("degraded_v1")
        
        # 规则 4: 预算受限（即使 governance 是 NORMAL，但预算不足时降级）
        budget_remaining = signals.get("budget_remaining", 1000.0)
        if budget_remaining < 100:
            return self.registry.get_plan("degraded_v1")
        
        # 规则 5: Evaluation 反馈回流（规则驱动、非学习型）
        if last_evaluation_feedback:
            last_failed = last_evaluation_feedback.get("failed", False)
            failure_type = last_evaluation_feedback.get("failure_type", "")
            if last_failed:
                # 规则映射（静态、可审计）：
                # - data_issue / data_unavailable → DEGRADED（跳过数据节点）
                # - execution_issue → MINIMAL（最小执行路径）
                # - cost_issue → DEGRADED（降级以节省成本）
                if failure_type in ["data_issue", "data_unavailable"]:
                    return self.registry.get_plan("degraded_v1")
                elif failure_type == "execution_issue":
                    return self.registry.get_plan("minimal_v1")
                elif failure_type == "cost_issue":
                    return self.registry.get_plan("degraded_v1")
        
        # 规则 6: 默认 NORMAL
        return self.registry.get_plan("normal_v1")
    
    def get_selection_reasoning(
        self,
        selected_plan: ExecutionPlan,
        governance_decision: GovernanceDecision,
        signals: Dict[str, Any],
        last_evaluation_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """生成计划选择的理由（用于审计）"""
        reasoning_parts = []
        
        execution_mode = governance_decision.execution_mode
        reasoning_parts.append(f"Governance mode: {execution_mode.value}")
        
        budget_remaining = signals.get("budget_remaining", 1000.0)
        if budget_remaining < 100:
            reasoning_parts.append(f"Budget constraint: {budget_remaining} < 100")
        
        if last_evaluation_feedback:
            last_failed = last_evaluation_feedback.get("failed", False)
            failure_type = last_evaluation_feedback.get("failure_type", "")
            if last_failed:
                reasoning_parts.append(f"Last evaluation failed: {failure_type}")
        
        return {
            "selected_plan_id": selected_plan.plan_id,
            "selected_plan_version": selected_plan.plan_version,
            "path_type": selected_plan.path_type.value,
            "reasoning": "; ".join(reasoning_parts),
            "governance_mode": execution_mode.value,
            "signals_used": {
                "budget_remaining": budget_remaining,
                "last_evaluation_failed": last_evaluation_feedback.get("failed", False) if last_evaluation_feedback else False
            }
        }

