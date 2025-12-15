"""
Prompt Loader: 可审计、可版本化的 prompt 文件系统
支持 .md 格式的版本化 prompt 文件
"""
import os
import json
import re
from typing import Dict, Any

class PromptLoader:
    def __init__(self, prompt_dir: str = "runtime/llm/prompts"):
        self.prompt_dir = prompt_dir
        os.makedirs(prompt_dir, exist_ok=True)
    
    def load_prompt(self, agent_name: str, prompt_type: str, version: str = "v1") -> Dict[str, Any]:
        """
        加载版本化 prompt 文件
        格式：{agent_name}_{prompt_type}_{version}.md
        """
        prompt_file = os.path.join(self.prompt_dir, f"{agent_name}_{prompt_type}_{version}.md")
        
        if not os.path.exists(prompt_file):
            # 返回默认 prompt
            return self._get_default_prompt(agent_name, prompt_type)
        
        return self._parse_markdown_prompt(prompt_file, version)
    
    def _parse_markdown_prompt(self, file_path: str, version: str) -> Dict[str, Any]:
        """解析 Markdown 格式的 prompt 文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取 system prompt
        system_match = re.search(r"## System Prompt\n\n(.*?)(?=\n##|$)", content, re.DOTALL)
        system_prompt = system_match.group(1).strip() if system_match else ""
        
        # 提取 user prompt template
        user_match = re.search(r"## User Prompt Template\n\n(.*?)(?=\n##|$)", content, re.DOTALL)
        user_prompt_template = user_match.group(1).strip() if user_match else ""
        
        # 提取 JSON Schema
        schema_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
        if schema_match:
            json_schema = json.loads(schema_match.group(1))
        else:
            # 尝试提取 JSON Schema 部分
            schema_section = re.search(r"## JSON Schema\n\n```json\n(.*?)\n```", content, re.DOTALL)
            if schema_section:
                json_schema = json.loads(schema_section.group(1))
            else:
                json_schema = {"type": "object", "properties": {}}
        
        return {
            "version": version,
            "system_prompt": system_prompt,
            "user_prompt_template": user_prompt_template,
            "json_schema": json_schema
        }
    
    def _get_default_prompt(self, agent_name: str, prompt_type: str) -> Dict[str, Any]:
        """返回默认 prompt（如果文件不存在）"""
        defaults = {
            "product_analyze": {
                "version": "1.0",
                "system_prompt": "You are a product specification interpreter. Analyze the given specification and provide structured understanding.",
                "user_prompt_template": "Analyze the following specification:\n\n{spec}\n\nProvide clarification summary, inferred constraints, missing fields, and assumptions.",
                "json_schema": {
                    "type": "object",
                    "required": ["clarification_summary", "inferred_constraints", "missing_fields", "assumptions"],
                    "properties": {
                        "clarification_summary": {"type": "string"},
                        "inferred_constraints": {"type": "array", "items": {"type": "string"}},
                        "missing_fields": {"type": "array", "items": {"type": "string"}},
                        "assumptions": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                }
            },
            "evaluation_review": {
                "version": "1.0",
                "system_prompt": "You are a quality evaluation reviewer. Review the execution results and provide evaluation insights.",
                "user_prompt_template": "Review the following execution context:\n\n{context_summary}\n\nProvide evaluation summary, potential risks, confidence level, and notable artifacts.",
                "json_schema": {
                    "type": "object",
                    "required": ["evaluation_summary", "potential_risks", "confidence_level", "notable_artifacts"],
                    "properties": {
                        "evaluation_summary": {"type": "string"},
                        "potential_risks": {"type": "array", "items": {"type": "string"}},
                        "confidence_level": {"type": "string", "enum": ["low", "medium", "high"]},
                        "notable_artifacts": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                }
            },
            "cost_reason": {
                "version": "1.0",
                "system_prompt": "You are a cost analysis assistant. Generate a clear reason for cost decisions.",
                "user_prompt_template": "Cost usage: {cost_usage}, Budget remaining: {budget_remaining}, Decision: {decision}\n\nGenerate a clear, professional reason for the cost decision.",
                "json_schema": {
                    "type": "object",
                    "required": ["decision_reason", "cost_flags"],
                    "properties": {
                        "decision_reason": {"type": "string"},
                        "cost_flags": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                }
            }
        }
        
        key = f"{agent_name}_{prompt_type}"
        return defaults.get(key, {
            "version": "1.0",
            "system_prompt": "You are an AI assistant.",
            "user_prompt_template": "{input}",
            "json_schema": {"type": "object", "properties": {}}
        })

