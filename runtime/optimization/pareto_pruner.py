"""
Pareto Frontier Pruner: 多目标路径剪枝
候选路径集合构建 + 多目标度量 + Pareto 前沿计算
选择仍由治理规则完成
"""
from typing import Dict, Any, List
from dataclasses import dataclass
from runtime.execution_plan.plan_definition import ExecutionPlan, PlanPath

@dataclass
class CandidatePath:
    """候选路径"""
    plan_id: str
    path_type: PlanPath
    success_proxy: float  # 来自 signals
    cost: float
    risk: float  # 0.0-1.0
    latency: float  # 秒

@dataclass
class ParetoFrontier:
    """Pareto 前沿"""
    candidates: List[CandidatePath]
    pruned_count: int
    prune_reasoning: List[str]

class ParetoPruner:
    """Pareto 前沿剪枝器（确定性规则）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "max_frontier_size": 5
        }
        self.version = "1.0"
    
    def compute_frontier(self, candidates: List[CandidatePath]) -> ParetoFrontier:
        """
        计算 Pareto 前沿（确定性规则）
        
        规则：多目标优化（最小化 cost、risk、latency，最大化 success_proxy）
        """
        if not candidates:
            return ParetoFrontier(
                candidates=[],
                pruned_count=0,
                prune_reasoning=[]
            )
        
        # 计算 Pareto 前沿（确定性算法）
        frontier = []
        pruned = []
        prune_reasoning = []
        
        for candidate in candidates:
            is_dominated = False
            dominated_by = None
            
            # 检查是否被其他候选支配
            for other in candidates:
                if other == candidate:
                    continue
                
                # 支配关系：other 在所有目标上都不差，且至少一个更好
                if (other.cost <= candidate.cost and
                    other.risk <= candidate.risk and
                    other.latency <= candidate.latency and
                    other.success_proxy >= candidate.success_proxy and
                    (other.cost < candidate.cost or
                     other.risk < candidate.risk or
                     other.latency < candidate.latency or
                     other.success_proxy > candidate.success_proxy)):
                    is_dominated = True
                    dominated_by = other.plan_id
                    break
            
            if not is_dominated:
                frontier.append(candidate)
            else:
                pruned.append(candidate)
                prune_reasoning.append(
                    f"{candidate.plan_id} dominated by {dominated_by}"
                )
        
        # 如果前沿太大，按规则剪枝（保留成本最低的）
        if len(frontier) > self.config["max_frontier_size"]:
            frontier.sort(key=lambda x: x.cost)
            excess = frontier[self.config["max_frontier_size"]:]
            for c in excess:
                prune_reasoning.append(f"{c.plan_id} pruned due to frontier size limit")
            frontier = frontier[:self.config["max_frontier_size"]]
        
        return ParetoFrontier(
            candidates=frontier,
            pruned_count=len(pruned) + (len(frontier) - len(frontier[:self.config["max_frontier_size"]])),
            prune_reasoning=prune_reasoning
        )
    
    def build_candidates_from_plans(
        self,
        plans: List[ExecutionPlan],
        signals: Dict[str, Any]
    ) -> List[CandidatePath]:
        """从计划构建候选路径（确定性规则）"""
        candidates = []
        
        for plan in plans:
            # 计算成本（确定性规则）
            total_cost = sum(node.cost_estimate for node in plan.nodes)
            
            # 计算风险（确定性规则：基于 risk_level）
            risk_scores = {
                "low": 0.2,
                "medium": 0.5,
                "high": 0.8,
                "critical": 1.0
            }
            max_risk = max(
                risk_scores.get(node.risk_level, 0.5)
                for node in plan.nodes
            )
            
            # 计算延迟（确定性规则：估算）
            estimated_latency = len(plan.nodes) * 5.0  # 简化：每个节点5秒
            
            # 成功代理（确定性规则：基于路径类型）
            success_proxy = {
                PlanPath.NORMAL: 1.0,
                PlanPath.DEGRADED: 0.7,
                PlanPath.MINIMAL: 0.5
            }.get(plan.path_type, 0.5)
            
            candidates.append(CandidatePath(
                plan_id=plan.plan_id,
                path_type=plan.path_type,
                success_proxy=success_proxy,
                cost=total_cost,
                risk=max_risk,
                latency=estimated_latency
            ))
        
        return candidates


