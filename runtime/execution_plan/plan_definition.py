"""
Execution Plan Definition: 条件 DAG 定义
显式、可审计的执行图对象
"""
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field

class PlanPath(str, Enum):
    """执行路径类型"""
    NORMAL = "normal"  # 完整交付路径
    DEGRADED = "degraded"  # 降级路径
    MINIMAL = "minimal"  # 最小可行路径

class NodeCondition:
    """节点条件：决定是否执行该节点"""
    def __init__(
        self,
        condition_type: str,
        condition_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
        condition_rule: Optional[str] = None
    ):
        self.condition_type = condition_type  # "always", "budget_check", "risk_check", "evaluation_feedback"
        self.condition_func = condition_func
        self.condition_rule = condition_rule  # 规则描述（用于审计）
    
    def evaluate(self, signals: Dict[str, Any]) -> bool:
        """评估条件是否满足"""
        if self.condition_func:
            return self.condition_func(signals)
        # 默认规则
        if self.condition_type == "always":
            return True
        elif self.condition_type == "budget_check":
            budget_remaining = signals.get("budget_remaining", 1000.0)
            return budget_remaining > 0
        elif self.condition_type == "risk_check":
            risk_level = signals.get("risk_level", "low")
            return risk_level not in ["high", "critical"]
        elif self.condition_type == "evaluation_feedback":
            # Evaluation 信号回流：如果上次失败，可能需要跳过某些节点
            last_eval_failed = signals.get("last_evaluation_failed", False)
            failure_type = signals.get("last_failure_type", "")
            # 规则：如果上次是数据问题，跳过数据相关节点（示例）
            return not (last_eval_failed and failure_type == "data_issue")
        return True

@dataclass
class PlanNode:
    """执行计划节点"""
    node_id: str
    agent_name: str
    description: str
    condition: NodeCondition
    required: bool = True  # 是否必需节点
    cost_estimate: float = 0.0  # 成本估算
    risk_level: str = "low"  # 风险级别
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "condition_type": self.condition.condition_type,
            "condition_rule": self.condition.condition_rule,
            "required": self.required,
            "cost_estimate": self.cost_estimate,
            "risk_level": self.risk_level
        }

@dataclass
class ExecutionPlan:
    """执行计划：显式、可审计的执行图"""
    plan_id: str
    plan_version: str
    path_type: PlanPath
    nodes: List[PlanNode] = field(default_factory=list)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "path_type": self.path_type.value,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes]
        }
    
    def get_executable_nodes(self, signals: Dict[str, Any]) -> List[PlanNode]:
        """根据当前信号获取可执行节点序列"""
        executable = []
        for node in self.nodes:
            if node.condition.evaluate(signals):
                executable.append(node)
        return executable
























