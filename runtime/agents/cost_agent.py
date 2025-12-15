"""
Cost Agent: 是否继续
LLM 增强版本：使用 LLM 生成 decision_reason 和 cost_flags，但 decision 由工程规则决定
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple
from runtime.llm.client_factory import create_llm_client
from runtime.llm.prompt_loader import PromptLoader

class CostAgent(BaseAgent):
    def __init__(self):
        super().__init__("Cost")
        self.llm_client = create_llm_client()
        self.prompt_loader = PromptLoader()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        职责：成本监控、预算约束、路径剪枝
        LLM 仅生成 decision_reason 和 cost_flags，decision 由工程规则决定
        """
        # 工程规则：decision 由预算决定（LLM 不参与决策）
        cost_usage = context.get("cost_usage", 0.0)
        budget_remaining = context.get("budget_remaining", 1000.0)
        
        decision = "continue" if budget_remaining > 0 else "terminate"
        base_reason = f"成本检查：已使用 {cost_usage}，剩余 {budget_remaining}"
        
        # LLM 调用：生成 decision_reason 和 cost_flags
        llm_output, llm_meta = await self._call_llm_for_reason(cost_usage, budget_remaining, decision)
        
        # 使用 LLM 生成的 reason（如果成功），否则使用 base_reason
        reason = base_reason
        if llm_meta.get("llm_used") and llm_output:
            llm_reason = llm_output.get("decision_reason", "")
            if llm_reason:
                reason = llm_reason
        
        return {
            "decision": decision,  # 工程规则决定，LLM 不参与
            "reason": reason,
            "cost_usage": cost_usage,
            "budget_remaining": budget_remaining,
            "llm_result": llm_meta,  # 完整的 LLM 元数据
            "state_update": {
                "cost_agent_executed": True,
                "cost_usage": cost_usage,
                "budget_remaining": budget_remaining,
                "cost_flags": llm_output.get("cost_flags", []) if llm_meta.get("llm_used") and llm_output else []
            }
        }
    
    async def _call_llm_for_reason(self, cost_usage: float, budget_remaining: float, decision: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """调用 LLM 生成 decision_reason 和 cost_flags"""
        prompt_data = self.prompt_loader.load_prompt("cost", "reasoner", "v1")
        
        # 构建 user prompt
        user_prompt = prompt_data["user_prompt_template"].format(
            cost_usage=cost_usage,
            budget_remaining=budget_remaining,
            decision=decision
        )
        
        # 调用 LLM（使用新的 generate_json 接口）
        result, meta = await self.llm_client.generate_json(
            system_prompt=prompt_data["system_prompt"],
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")}
        )
        
        return result, meta
    
    def get_governing_question(self) -> str:
        return "是否继续？预算是否允许？"

