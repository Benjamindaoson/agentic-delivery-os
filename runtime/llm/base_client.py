"""
Base LLM Client: Provider-Agnostic Interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import hashlib
import json

class LLMClient(ABC):
    """统一的 LLM 客户端接口"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timeout_sec = config.get("timeout_sec", 20)
        self.max_retries = config.get("max_retries", 2)
        self.temperature = config.get("temperature", 0.0)
        self.max_tokens = config.get("max_tokens", 512)
        self.top_p = config.get("top_p", 1.0)
    
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        生成严格 JSON 输出
        
        Returns:
            (result: dict, llm_meta: dict)
            result: LLM 生成的 JSON 对象（验证后）或 fallback
            llm_meta: LLM 调用元数据（provider, model, hashes, etc.）
        """
        prompt_hash = self._hash_prompt(system_prompt, user_prompt)
        meta = meta or {}
        
        try:
            # 调用具体 provider 实现
            raw_output, retries = await self._call_provider(system_prompt, user_prompt, schema)
            
            # 验证 JSON Schema
            validation_result = self._validate_json_schema(raw_output, schema)
            if not validation_result["valid"]:
                return (
                    self._get_fallback_output(schema),
                    {
                        "llm_used": False,
                        "fallback_used": True,
                        "failure_code": "llm_schema_invalid",
                        "prompt_hash": prompt_hash,
                        "validation_errors": validation_result["errors"]
                    }
                )
            
            # 生成 output hash
            output_hash = self._hash_output(raw_output)
            
            return (
                raw_output,
                {
                    "llm_used": True,
                    "fallback_used": False,
                    "failure_code": None,
                    "provider": self.get_provider_name(),
                    "model_name": self.get_model_name(),
                    "prompt_version": meta.get("prompt_version", "1.0"),
                    "sampling_params": {
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "top_p": self.top_p
                    },
                    "timeout_sec": self.timeout_sec,
                    "retries": retries,
                    "prompt_hash": prompt_hash,
                    "output_hash": output_hash,
                    "output_summary": self._generate_output_summary(raw_output)
                }
            )
        except Exception as e:
            # 任何失败都返回 fallback
            failure_code = self._classify_error(e)
            return (
                self._get_fallback_output(schema),
                {
                    "llm_used": False,
                    "fallback_used": True,
                    "failure_code": failure_code,
                    "prompt_hash": prompt_hash,
                    "error": str(e),
                    "provider": self.get_provider_name(),
                    "model_name": self.get_model_name()
                }
            )
    
    @abstractmethod
    async def _call_provider(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """调用具体 provider 的 API，返回 (output, retries)"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """返回 provider 名称"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """返回 model 名称"""
        pass
    
    def _validate_json_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """验证 JSON Schema"""
        errors = []
        
        # 检查 additionalProperties
        additional_props_allowed = schema.get("additionalProperties", True)
        if additional_props_allowed is False:
            allowed_fields = set(schema.get("properties", {}).keys())
            actual_fields = set(data.keys())
            extra_fields = actual_fields - allowed_fields
            if extra_fields:
                errors.append(f"Additional properties not allowed: {', '.join(extra_fields)}")
        
        # 检查必需字段
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
        
        # 检查字段类型和 enum
        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                if field in data:
                    expected_type = field_schema.get("type")
                    if expected_type:
                        actual_type = type(data[field]).__name__
                        type_map = {
                            "string": "str",
                            "number": ("int", "float"),
                            "integer": "int",
                            "boolean": "bool",
                            "object": "dict",
                            "array": "list"
                        }
                        if expected_type in type_map:
                            expected_python_types = type_map[expected_type]
                            if isinstance(expected_python_types, tuple):
                                if actual_type not in expected_python_types:
                                    errors.append(f"Field {field}: expected {expected_type}, got {actual_type}")
                            elif actual_type != expected_python_types:
                                errors.append(f"Field {field}: expected {expected_type}, got {actual_type}")
                    
                    # 检查 enum
                    if "enum" in field_schema:
                        if data[field] not in field_schema["enum"]:
                            errors.append(f"Field {field}: value '{data[field]}' not in enum {field_schema['enum']}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _get_fallback_output(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """生成 fallback 输出"""
        fallback = {}
        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                field_type = field_schema.get("type")
                if field_type == "string":
                    fallback[field] = ""
                elif field_type == "array":
                    fallback[field] = []
                elif field_type == "object":
                    fallback[field] = {}
                elif field_type in ["number", "integer"]:
                    fallback[field] = 0
                elif field_type == "boolean":
                    fallback[field] = False
        return fallback
    
    def _classify_error(self, error: Exception) -> str:
        """分类错误类型"""
        error_str = str(error).lower()
        if "timeout" in error_str:
            return "llm_timeout"
        elif "json" in error_str or "parse" in error_str:
            return "llm_parse_failed"
        elif "http" in error_str or "4" in error_str or "5" in error_str:
            return "llm_http_error"
        elif "schema" in error_str or "validation" in error_str:
            return "llm_schema_invalid"
        else:
            return "llm_unknown_error"
    
    def _hash_prompt(self, system_prompt: str, user_prompt: str) -> str:
        """生成 prompt hash"""
        combined = f"{system_prompt}\n\n{user_prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _hash_output(self, output: Dict[str, Any]) -> str:
        """生成 output hash"""
        output_str = json.dumps(output, sort_keys=True)
        return hashlib.sha256(output_str.encode()).hexdigest()[:16]
    
    def _generate_output_summary(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """生成 output summary（不包含原始内容）"""
        summary = {}
        for key, value in output.items():
            if isinstance(value, str):
                summary[key] = f"string({len(value)} chars)"
            elif isinstance(value, list):
                summary[key] = f"array({len(value)} items)"
            elif isinstance(value, dict):
                summary[key] = f"object({len(value)} keys)"
            else:
                summary[key] = type(value).__name__
        return summary

