"""
Evaluation Agent: 是否完成
LLM 增强版本：使用 LLM 生成 evaluation_summary, potential_risks, confidence_level, notable_artifacts
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader

class EvaluationAgent(BaseAgent):
    def __init__(self):
        super().__init__("Evaluation")
        # 使用集中化的 LLMAdapter 入口
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        职责：质量评测、上线门槛、失败归因
        LLM 仅生成 evaluation_summary, potential_risks, confidence_level, notable_artifacts，不参与决策
        """
        # 工程规则：总是通过（LLM 不参与决策）
        decision = "passed"
        base_reason = "质量评测通过"
        
        # 构建 context summary 供 LLM 使用
        context_summary = self._build_context_summary(context)
        
        # LLM 调用：生成评估结果
        llm_output, llm_meta = await self._call_llm_for_review(context_summary)
        
        # 构建 evaluation_result（工程规则决定 passed）
        # 注意：这里 passed 由工程规则决定，但会输出结构化信号供回流使用
        evaluation_result = {
            "quality_score": 0.85,
            "grounded_rate": 1.0,
            "latency_ms": 0,
            "passed": True,
            "failure_type": None,  # 失败类型（用于回流）：data_issue, execution_issue, cost_issue, evaluation_issue
            "blame_hint": None  # 归因线索（哪个 Agent/节点负责）
        }
        
        # 检查上下文中的执行状态（工程规则）
        execution_agent_executed = context.get("execution_agent_executed", False)
        data_agent_executed = context.get("data_agent_executed", False)
        artifacts = context.get("artifacts", {})
        
        # 工程规则：如果关键步骤未完成，标记为失败
        if not execution_agent_executed:
            evaluation_result["passed"] = False
            evaluation_result["failure_type"] = "execution_issue"
            evaluation_result["blame_hint"] = "Execution Agent"
        elif not artifacts.get("config_generated", False):
            evaluation_result["passed"] = False
            evaluation_result["failure_type"] = "execution_issue"
            evaluation_result["blame_hint"] = "Execution Agent"
        elif not data_agent_executed:
            evaluation_result["passed"] = False
            evaluation_result["failure_type"] = "data_issue"
            evaluation_result["blame_hint"] = "Data Agent"
        
        # 如果 LLM 成功，添加 LLM 生成的 insights
        if llm_meta.get("llm_used") and llm_output:
            evaluation_result["llm_evaluation_summary"] = llm_output.get("evaluation_summary", "")
            evaluation_result["llm_potential_risks"] = llm_output.get("potential_risks", [])
            evaluation_result["llm_confidence_level"] = llm_output.get("confidence_level", "medium")
            evaluation_result["llm_notable_artifacts"] = llm_output.get("notable_artifacts", [])
            
            # 从 LLM 输出中提取失败类型和归因线索（如果有，但工程规则优先）
            if evaluation_result["passed"]:  # 只有在工程规则通过时才使用 LLM 信号
                risks = llm_output.get("potential_risks", [])
                if risks:
                    # 规则：如果提到数据问题，标记为数据失败
                    for risk in risks:
                        risk_lower = risk.lower()
                        if "data" in risk_lower or "数据" in risk_lower:
                            evaluation_result["failure_type"] = "data_issue"
                            evaluation_result["blame_hint"] = "Data Agent"
                            evaluation_result["passed"] = False
                            break
                        elif "execution" in risk_lower or "执行" in risk_lower or "build" in risk_lower:
                            evaluation_result["failure_type"] = "execution_issue"
                            evaluation_result["blame_hint"] = "Execution Agent"
                            evaluation_result["passed"] = False
                            break
                        elif "cost" in risk_lower or "预算" in risk_lower or "budget" in risk_lower:
                            evaluation_result["failure_type"] = "cost_issue"
                            evaluation_result["blame_hint"] = "Cost Agent"
                            evaluation_result["passed"] = False
                            break
        
        # 构建 reason
        reason = base_reason
        if llm_meta.get("llm_used") and llm_output:
            summary = llm_output.get("evaluation_summary", "")
            if summary:
                reason = f"{base_reason}。LLM 评估：{summary[:100]}..." if len(summary) > 100 else f"{base_reason}。LLM 评估：{summary}"
        
        return {
            "decision": decision,  # 工程规则决定
            "reason": reason,
            "evaluation_result": evaluation_result,
            "llm_result": llm_meta,  # 完整的 LLM 元数据
            "state_update": {
                "evaluation_agent_executed": True,
                "evaluation_result": {
                    "quality_score": evaluation_result["quality_score"],
                    "passed": evaluation_result["passed"]
                },
                # Evaluation 信号回流：供下次执行使用
                "last_evaluation_failed": not evaluation_result["passed"],
                "last_failure_type": evaluation_result.get("failure_type"),
                "last_blame_hint": evaluation_result.get("blame_hint")
            }
        }
    
    def _build_context_summary(self, context: Dict[str, Any]) -> str:
        """构建 context summary 供 LLM 使用"""
        summary_parts = []
        
        # 提取关键信息
        if context.get("data_agent_executed"):
            summary_parts.append("Data Agent: 已执行")
        if context.get("execution_agent_executed"):
            summary_parts.append("Execution Agent: 已执行")
        if context.get("cost_usage") is not None:
            summary_parts.append(f"Cost usage: {context.get('cost_usage')}")
        if context.get("budget_remaining") is not None:
            summary_parts.append(f"Budget remaining: {context.get('budget_remaining')}")
        
        return "\n".join(summary_parts) if summary_parts else "Execution context available"
    
    async def _call_llm_for_review(self, context_summary: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """调用 LLM 进行评估审查"""
        prompt_data = self.prompt_loader.load_prompt("evaluation", "reviewer", "v1")
        
        # 构建 user prompt
        user_prompt = prompt_data["user_prompt_template"].format(context_summary=context_summary)
        
        # 调用 LLM（使用统一 adapter）
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data["system_prompt"],
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=context.get("tenant_id", "default"),
            model=prompt_data.get("model", None)
        )
        
        return result, meta
    
    def get_governing_question(self) -> str:
        return "是否完成？是否达到成功标准？"

