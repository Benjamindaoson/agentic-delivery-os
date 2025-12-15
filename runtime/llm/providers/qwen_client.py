"""
Qwen Client: 默认 LLM Provider
使用 Qwen Chat Completion API
"""
import os
import json
import asyncio
from typing import Dict, Any, Tuple
import aiohttp
from runtime.llm.base_client import LLMClient

class QwenClient(LLMClient):
    """Qwen LLM 客户端实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("QWEN_API_KEY", "")
        self.base_url = config.get("base_url") or os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model_name = config.get("model") or os.getenv("QWEN_MODEL", "qwen-turbo")
    
    async def _call_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """调用 Qwen API"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "response_format": {"type": "json_object"} if schema else None
        }
        
        payload = {k: v for k, v in payload.items() if v is not None}
        
        retries = 0
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_sec)) as session:
            for attempt in range(self.max_retries + 1):
                try:
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status == 429 or response.status >= 500:
                            if attempt < self.max_retries:
                                retries = attempt + 1
                                await asyncio.sleep(2 ** attempt)
                                continue
                        elif response.status >= 400:
                            error_data = await response.json()
                            raise Exception(f"API error {response.status}: {error_data}")
                        
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        output = json.loads(content)
                        return output, retries
                        
                except asyncio.TimeoutError:
                    if attempt < self.max_retries:
                        retries = attempt + 1
                        continue
                    raise Exception("LLM request timeout")
                except json.JSONDecodeError as e:
                    raise Exception(f"Failed to parse LLM response as JSON: {e}")
        
        raise Exception("Max retries exceeded")
    
    def get_provider_name(self) -> str:
        return "qwen"
    
    def get_model_name(self) -> str:
        return self.model_name

