"""
Plan Registry: 执行计划注册表
定义所有可用的执行计划（规则驱动、非学习型）
"""
from typing import Dict, List
from runtime.execution_plan.plan_definition import (
    ExecutionPlan, PlanNode, NodeCondition, PlanPath
)

class PlanRegistry:
    """计划注册表：所有可用的执行计划"""
    
    def __init__(self):
        self.plans: Dict[str, ExecutionPlan] = {}
        self._register_default_plans()
    
    def _register_default_plans(self):
        """注册默认计划（规则驱动、非学习型）"""
        
        # 1. NORMAL 路径：完整交付路径
        normal_plan = ExecutionPlan(
            plan_id="normal_v1",
            plan_version="1.0",
            path_type=PlanPath.NORMAL,
            description="完整交付路径：Product → Data → Execution → Evaluation"
        )
        normal_plan.nodes = [
            PlanNode(
                node_id="product",
                agent_name="Product",
                description="需求澄清与 Spec 验证",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=10.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="cost_after_product",
                agent_name="Cost",
                description="成本检查（Product 后）",
                condition=NodeCondition("budget_check", condition_rule="Execute if budget > 0"),
                required=True,
                cost_estimate=0.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="data",
                agent_name="Data",
                description="数据接入与验证",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=50.0,
                risk_level="medium"
            ),
            PlanNode(
                node_id="cost_after_data",
                agent_name="Cost",
                description="成本检查（Data 后）",
                condition=NodeCondition("budget_check", condition_rule="Execute if budget > 0"),
                required=True,
                cost_estimate=0.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="execution",
                agent_name="Execution",
                description="工程执行与构建",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=200.0,
                risk_level="medium"
            ),
            PlanNode(
                node_id="cost_after_execution",
                agent_name="Cost",
                description="成本检查（Execution 后）",
                condition=NodeCondition("budget_check", condition_rule="Execute if budget > 0"),
                required=True,
                cost_estimate=0.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="evaluation",
                agent_name="Evaluation",
                description="质量评测与验收",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=30.0,
                risk_level="low"
            )
        ]
        self.plans["normal_v1"] = normal_plan
        
        # 2. DEGRADED 路径：降级路径（跳过高风险/高成本节点）
        degraded_plan = ExecutionPlan(
            plan_id="degraded_v1",
            plan_version="1.0",
            path_type=PlanPath.DEGRADED,
            description="降级路径：跳过高风险节点，使用最小功能集"
        )
        degraded_plan.nodes = [
            PlanNode(
                node_id="product",
                agent_name="Product",
                description="需求澄清与 Spec 验证",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=10.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="cost_after_product",
                agent_name="Cost",
                description="成本检查（Product 后）",
                condition=NodeCondition("budget_check", condition_rule="Execute if budget > 0"),
                required=True,
                cost_estimate=0.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="data",
                agent_name="Data",
                description="数据接入与验证（简化）",
                condition=NodeCondition(
                    "evaluation_feedback",
                    condition_rule="Skip if last evaluation failed with data_issue, otherwise execute if budget > 50",
                    condition_func=lambda signals: (
                        not (signals.get("last_evaluation_failed", False) and 
                             signals.get("last_failure_type") == "data_issue")
                    ) and signals.get("budget_remaining", 0) > 50
                ),
                required=False,
                cost_estimate=30.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="execution",
                agent_name="Execution",
                description="工程执行（最小功能）",
                condition=NodeCondition("budget_check", condition_rule="Execute if budget > 100"),
                required=True,
                cost_estimate=100.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="evaluation",
                agent_name="Evaluation",
                description="基础评测",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=20.0,
                risk_level="low"
            )
        ]
        self.plans["degraded_v1"] = degraded_plan
        
        # 3. MINIMAL 路径：最小可行路径
        minimal_plan = ExecutionPlan(
            plan_id="minimal_v1",
            plan_version="1.0",
            path_type=PlanPath.MINIMAL,
            description="最小可行路径：仅核心功能"
        )
        minimal_plan.nodes = [
            PlanNode(
                node_id="product",
                agent_name="Product",
                description="需求澄清（最小）",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=5.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="execution",
                agent_name="Execution",
                description="最小工程执行",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=50.0,
                risk_level="low"
            ),
            PlanNode(
                node_id="evaluation",
                agent_name="Evaluation",
                description="基础验收",
                condition=NodeCondition("always", condition_rule="Always execute"),
                required=True,
                cost_estimate=10.0,
                risk_level="low"
            )
        ]
        self.plans["minimal_v1"] = minimal_plan
    
    def get_plan(self, plan_id: str) -> ExecutionPlan:
        """获取指定计划"""
        return self.plans.get(plan_id)
    
    def list_plans(self) -> List[ExecutionPlan]:
        """列出所有计划"""
        return list(self.plans.values())

