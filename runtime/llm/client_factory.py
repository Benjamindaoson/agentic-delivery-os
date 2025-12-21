"""
LLM Client Factory: 根据配置创建对应的 LLM Client
"""
import os
import yaml
from typing import Dict, Any
from runtime.llm.providers.qwen_client import QwenClient
from runtime.llm.providers.openai_client import OpenAIClient
from runtime.llm.mock_client import MockLLMClient
from runtime.llm.base_client import LLMClient

def create_llm_client(config_path: str = "configs/system.yaml") -> "LLMClient":
    """
    根据配置创建 LLM Client
    默认使用 Qwen
    """
    # 读取配置
    llm_config = _load_llm_config(config_path)
    
    # 模式切换：支持 mock | real
    mode = os.getenv("LLM_MODE", llm_config.get("mode", llm_config.get("provider_mode", "mock"))).lower()

    # 从环境变量或配置获取 provider（仅在 real 模式使用）
    provider = os.getenv("LLM_PROVIDER", llm_config.get("provider", "qwen")).lower()
    
    # 构建 client config
    client_config = {
        "timeout_sec": llm_config.get("timeout_sec", 20),
        "max_retries": llm_config.get("max_retries", 2),
        "temperature": llm_config.get("temperature", 0.0),
        "max_tokens": llm_config.get("max_tokens", 512),
        "top_p": llm_config.get("top_p", 1.0),
        "model": llm_config.get("model"),
        "api_key": llm_config.get("api_key"),
        "base_url": llm_config.get("base_url")
    }
    
    # 如果模式为 mock，返回 MockLLMClient（deterministic）
    if mode == "mock":
        return MockLLMClient(client_config)

    # 否则尝试创建真实 provider client
    if provider == "qwen":
        return QwenClient(client_config)
    elif provider == "openai":
        return OpenAIClient(client_config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def _load_llm_config(config_path: str) -> Dict[str, Any]:
    """从配置文件加载 LLM 配置"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("llm", {})
    except FileNotFoundError:
        # 配置文件不存在，返回默认配置
        return {
            "provider": "qwen",
            "timeout_sec": 20,
            "max_retries": 2,
            "temperature": 0.0,
            "max_tokens": 512,
            "top_p": 1.0
        }
























