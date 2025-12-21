"""
LLM Adapter singleton access point.
Provides get_llm_adapter() to ensure all agents use the same adapter instance.
"""
from typing import Optional
from runtime.llm.adapter import LLMAdapter

_ADAPTER: Optional[LLMAdapter] = None

def get_llm_adapter(config_path: str = "configs/system.yaml") -> LLMAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = LLMAdapter(config_path=config_path)
    return _ADAPTER

# LLM 模块：最小、真实、可控的 LLM 能力
























