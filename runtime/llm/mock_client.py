"""
Deterministic Mock LLM Client for dev / tests.
Produces canned JSON responses matching the requested schema.
"""
from typing import Dict, Any, Tuple
from runtime.llm.base_client import LLMClient

class MockLLMClient(LLMClient):
    """简单的 Mock LLM 实现，返回确定性输出，适合开发/测试"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})

    async def _call_provider(self, system_prompt: str, user_prompt: str, schema: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        返回一个基于 schema 的空白但有效的 JSON 对象（deterministic）
        返回 (output, retries)
        """
        # 生成 deterministic output: 对每个 required 字段填充类型默认值
        output = {}
        props = schema.get("properties", {}) if schema else {}
        required = schema.get("required", []) if schema else []
        for k, v in props.items():
            t = v.get("type")
            if t == "string":
                output[k] = f"mock_{k}"
            elif t == "array":
                output[k] = []
            elif t == "object":
                output[k] = {}
            elif t in ("number", "integer"):
                output[k] = 0
            elif t == "boolean":
                output[k] = False
            else:
                output[k] = None

        # ensure required fields exist
        for r in required:
            if r not in output:
                output[r] = ""

        # retries = 0 for mock
        return output, 0

    def get_provider_name(self) -> str:
        return "mock"

    def get_model_name(self) -> str:
        return "mock-model"


