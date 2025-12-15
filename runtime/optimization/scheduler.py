"""
Cost-Aware Scheduler: 确定性调度优化
基于 DAG 的关键路径优先（Critical Path Priority）
阶段预算分配（Spec/Build/Verify/Govern 可配置权重）
Anytime 输出策略：预算/时间触顶时输出最佳可交付结果
"""
from typing import Dict, Any, List
from dataclasses import dataclass
from runtime.execution_plan.plan_definition import ExecutionPlan, PlanNode

@dataclass
class SchedulePlan:
    """调度计划"""
    node_priorities: List[Dict[str, Any]]  # 节点优先级列表
    stage_budget_allocation: Dict[str, float]  # 阶段预算表
    schedule_evidence: Dict[str, Any]  # 为什么这么排

class CostAwareScheduler:
    """成本感知调度器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "stage_weights": {
                "spec": 0.1,
                "build": 0.6,
                "verify": 0.2,
                "govern": 0.1
            },
            "critical_path_bonus": 1.5  # 关键路径优先级加成
        }
        self.version = "1.0"
    
    def schedule(self, plan: ExecutionPlan, total_budget: float) -> SchedulePlan:
        """
        生成调度计划
        
        Args:
            plan: 执行计划
            total_budget: 总预算
        
        Returns:
            SchedulePlan: 调度计划
        """
        # 1. 计算关键路径（简化：按依赖关系）
        critical_nodes = self._identify_critical_path(plan)
        
        # 2. 计算节点优先级
        node_priorities = []
        for node in plan.nodes:
            priority_score = self._calculate_priority(node, critical_nodes)
            node_priorities.append({
                "node_id": node.node_id,
                "agent_name": node.agent_name,
                "priority_score": priority_score,
                "is_critical": node.node_id in critical_nodes,
                "cost_estimate": node.cost_estimate
            })
        
        # 按优先级排序
        node_priorities.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # 3. 阶段预算分配
        stage_budget_allocation = {}
        for stage, weight in self.config["stage_weights"].items():
            stage_budget_allocation[stage] = total_budget * weight
        
        # 4. 生成证据
        schedule_evidence = {
            "scheduler_version": self.version,
            "critical_nodes": critical_nodes,
            "total_budget": total_budget,
            "stage_weights": self.config["stage_weights"],
            "priorities_topk": node_priorities[:5]  # Top-5
        }
        
        return SchedulePlan(
            node_priorities=node_priorities,
            stage_budget_allocation=stage_budget_allocation,
            schedule_evidence=schedule_evidence
        )
    
    def _identify_critical_path(self, plan: ExecutionPlan) -> List[str]:
        """识别关键路径（简化实现）"""
        # 简化：高成本节点 + 必需节点
        critical = []
        for node in plan.nodes:
            if node.required or node.cost_estimate > 100:
                critical.append(node.node_id)
        return critical
    
    def _calculate_priority(self, node: PlanNode, critical_nodes: List[str]) -> float:
        """计算节点优先级"""
        base_priority = 1.0
        
        # 关键路径加成
        if node.node_id in critical_nodes:
            base_priority *= self.config["critical_path_bonus"]
        
        # 必需节点加成
        if node.required:
            base_priority *= 1.2
        
        # 成本倒序（低成本优先，但关键路径优先）
        if node.node_id not in critical_nodes:
            base_priority /= (1 + node.cost_estimate / 100)
        
        return base_priority


