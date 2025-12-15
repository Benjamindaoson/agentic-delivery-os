"""
Goal Satisfaction Layer: 用户目标完成度
DONE / PARTIAL / NOT_DONE
与 COMPLETED/FAILED 解耦：COMPLETED 也可能 PARTIAL
"""
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class GoalStatus(str, Enum):
    """目标状态"""
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    NOT_DONE = "NOT_DONE"

@dataclass
class GoalSatisfaction:
    """目标完成度"""
    goal_status: GoalStatus
    completion_breakdown: List[Dict[str, Any]]  # 子目标列表
    user_next_actions: List[str]  # 下一步要用户补什么（结构化）
    missing_requirements: List[str]  # 缺失需求

class GoalSatisfactionEvaluator:
    """目标完成度评估器"""
    
    def __init__(self):
        self.version = "1.0"
    
    def evaluate(self, trace_data: Dict[str, Any], spec: Dict[str, Any]) -> GoalSatisfaction:
        """
        评估目标完成度
        
        Args:
            trace_data: trace 数据
            spec: 用户 spec
        
        Returns:
            GoalSatisfaction: 目标完成度
        """
        # 提取关键信息
        final_state = trace_data.get("state_transitions", [{}])[-1].get("state", "UNKNOWN")
        agent_reports = trace_data.get("agent_reports", [])
        governance_decisions = trace_data.get("governance_decisions", [])
        
        # 判断目标状态（确定性规则）
        if final_state == "COMPLETED":
            # 检查是否有降级或暂停
            has_degraded = any(
                d.get("execution_mode") in ["degraded", "minimal"]
                for d in governance_decisions
            )
            has_paused = any(
                d.get("execution_mode") == "paused"
                for d in governance_decisions
            )
            
            if has_paused:
                goal_status = GoalStatus.NOT_DONE
            elif has_degraded:
                goal_status = GoalStatus.PARTIAL
            else:
                goal_status = GoalStatus.DONE
        else:
            goal_status = GoalStatus.NOT_DONE
        
        # 构建子目标完成情况
        completion_breakdown = []
        for report in agent_reports:
            agent_name = report.get("agent_name")
            decision = report.get("decision")
            status = report.get("status")
            
            completion_breakdown.append({
                "agent": agent_name,
                "status": "completed" if status == "success" else "failed",
                "decision": decision
            })
        
        # 生成用户下一步行动（结构化）
        user_next_actions = []
        if goal_status == GoalStatus.NOT_DONE:
            user_next_actions.append("检查失败原因")
            user_next_actions.append("补充缺失信息")
            user_next_actions.append("重新提交任务")
        elif goal_status == GoalStatus.PARTIAL:
            user_next_actions.append("检查降级原因")
            user_next_actions.append("考虑增加预算")
            user_next_actions.append("评估部分结果是否可用")
        
        # 缺失需求
        missing_requirements = []
        if goal_status != GoalStatus.DONE:
            missing_requirements.append("完整执行路径")
            if goal_status == GoalStatus.NOT_DONE:
                missing_requirements.append("关键 Agent 成功执行")
        
        return GoalSatisfaction(
            goal_status=goal_status,
            completion_breakdown=completion_breakdown,
            user_next_actions=user_next_actions,
            missing_requirements=missing_requirements
        )


