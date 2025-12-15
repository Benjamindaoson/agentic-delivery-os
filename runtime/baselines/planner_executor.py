"""
Planner Executor Baseline
有规划 + 执行，无成本治理，无失败回流闭环，无 conflict hard gate
"""
from typing import Dict, Any
from runtime.agents.product_agent import ProductAgent
from runtime.agents.execution_agent import ExecutionAgent

class PlannerExecutor:
    """Planner Executor 基线系统"""
    
    def __init__(self):
        self.product_agent = ProductAgent()
        self.execution_agent = ExecutionAgent()
        self.version = "1.0"
    
    async def execute(self, task_spec: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """执行任务（规划 + 执行，无治理）"""
        context = {"spec": task_spec}
        
        # 规划阶段
        product_result = await self.product_agent.execute(context, task_id)
        
        # 执行阶段
        context.update(product_result.get("state_update", {}))
        execution_result = await self.execution_agent.execute(context, task_id)
        
        # 无成本治理、无失败回流、无冲突检测
        return {
            "status": "COMPLETED" if execution_result.get("decision") == "execution_complete" else "FAILED",
            "trace": {
                "agent_executions": [
                    {
                        "agent": "Product",
                        "decision": product_result.get("decision"),
                        "reason": product_result.get("reason")
                    },
                    {
                        "agent": "Execution",
                        "decision": execution_result.get("decision"),
                        "reason": execution_result.get("reason")
                    }
                ],
                "governance_decisions": [],
                "agent_reports": [],
                "execution_plan": {}
            },
            "cost": 0.0
        }


