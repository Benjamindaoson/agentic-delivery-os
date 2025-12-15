"""
Naive Agent Baseline
单 Agent，无治理，无显式失败策略，无成本剪枝
"""
from typing import Dict, Any
from runtime.agents.product_agent import ProductAgent

class NaiveAgent:
    """Naive Agent 基线系统"""
    
    def __init__(self):
        self.agent = ProductAgent()
        self.version = "1.0"
    
    async def execute(self, task_spec: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """执行任务（简化：只执行 Product Agent）"""
        context = {"spec": task_spec}
        result = await self.agent.execute(context, task_id)
        
        # 简化：直接返回结果，无治理、无失败策略、无成本剪枝
        return {
            "status": "COMPLETED" if result.get("decision") == "proceed" else "FAILED",
            "trace": {
                "agent_executions": [{
                    "agent": "Product",
                    "decision": result.get("decision"),
                    "reason": result.get("reason")
                }],
                "governance_decisions": [],
                "agent_reports": [],
                "execution_plan": {}
            },
            "cost": 0.0
        }


