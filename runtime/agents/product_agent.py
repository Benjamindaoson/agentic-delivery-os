"""
Product Agent: 是否启动？需求是否清晰？
LLM 增强版本：使用 LLM 生成 clarification_summary, inferred_constraints, missing_fields, assumptions
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple
import json
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader

class ProductAgent(BaseAgent):
    def __init__(self):
        super().__init__("Product")
        # 使用集中化的 LLMAdapter 入口，禁止直接使用 client
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        职责：需求澄清、Spec UX、交付目标冻结
        LLM 仅生成 clarification_summary, inferred_constraints, missing_fields, assumptions，不参与决策
        """
        spec = context.get("spec", {})
        
        # 工程规则：总是通过验证（LLM 不参与决策）
        decision = "proceed"
        base_reason = "Spec 验证通过"
        
        # LLM 调用：生成结构化分析（传入 task_id, tenant）
        llm_output, llm_meta = await self._call_llm_for_analysis(spec, task_id=task_id, tenant_id=context.get("tenant_id", "default"))
        
        # 构建 state_update（包含 LLM 输出，如果有）
        state_update = {
            "product_agent_executed": True,
            "spec_validated": True
        }
        
        if llm_meta.get("llm_used") and llm_output:
            state_update["clarification_summary"] = llm_output.get("clarification_summary", "")
            state_update["inferred_constraints"] = llm_output.get("inferred_constraints", [])
            state_update["missing_fields"] = llm_output.get("missing_fields", [])
            state_update["assumptions"] = llm_output.get("assumptions", [])
        
        # 构建 reason（包含 LLM 生成的 summary，如果有）
        reason = base_reason
        if llm_meta.get("llm_used") and llm_output:
            summary = llm_output.get("clarification_summary", "")
            if summary:
                reason = f"{base_reason}。LLM 分析：{summary[:100]}..." if len(summary) > 100 else f"{base_reason}。LLM 分析：{summary}"
        
        return {
            "decision": decision,  # 工程规则决定
            "reason": reason,
            "llm_result": llm_meta,  # 完整的 LLM 元数据
            "state_update": state_update
        }
    
    async def _call_llm_for_analysis(self, spec: Dict[str, Any], task_id: str = None, tenant_id: str = "default") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """调用 LLM 进行 spec 分析"""
        prompt_data = self.prompt_loader.load_prompt("product", "spec_interpreter", "v1")
        
        # 构建 user prompt
        spec_str = json.dumps(spec, indent=2, ensure_ascii=False) if spec else "{}"
        user_prompt = prompt_data["user_prompt_template"].format(spec=spec_str)
        
        # 调用 LLM（使用新的 generate_json 接口）
        # 使用 adapter.call(...)，adapter 负责限流/重试/计费/trace 写入
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data["system_prompt"],
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=tenant_id,
            model=prompt_data.get("model", None)
        )
        
        return result, meta
    
    def get_governing_question(self) -> str:
        return "是否启动？需求是否清晰？"

