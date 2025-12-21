# LLM 集成说明

## 概述

系统已集成最小、真实、可控的 LLM 能力，用于增强三个 Agent 的输出：
- **Product Agent**: 生成 clarification_summary 和 inferred_constraints
- **Evaluation Agent**: 生成 evaluation_summary, potential_risks, confidence_level
- **Cost Agent**: 生成 decision_reason

## 关键原则

1. **LLM 不参与系统决策**
   - 所有 decision 由工程规则决定
   - LLM 仅提供建议和增强 reason 文本

2. **LLM 失败不影响系统完成**
   - 任何 LLM 调用失败时，使用 fallback
   - 系统必须能进入 COMPLETED 状态

3. **严格 JSON Schema 校验**
   - 所有 LLM 输出必须符合预定义 JSON Schema
   - 校验失败时使用 fallback

## 配置

通过环境变量配置 LLM：

```bash
# LLM Provider (openai / anthropic / azure_openai)
LLM_PROVIDER=openai

# API Key
LLM_API_KEY=your_api_key_here

# Model Name
LLM_MODEL=gpt-3.5-turbo

# Base URL (仅 Azure OpenAI 需要)
LLM_BASE_URL=https://your-resource.openai.azure.com
```

## Prompt 文件

Prompt 文件位于 `runtime/llm/prompts/`：
- `product_analyze.json`: Product Agent 的 prompt
- `evaluation_review.json`: Evaluation Agent 的 prompt
- `cost_reason.json`: Cost Agent 的 prompt

每个 prompt 文件包含：
- `version`: Prompt 版本
- `system_prompt`: System prompt
- `user_prompt_template`: User prompt 模板
- `json_schema`: JSON Schema 定义

## Trace 记录

`system_trace.json` 中每个 Agent 执行记录包含 `llm_info` 字段：

```json
{
  "llm_info": {
    "llm_used": true,
    "provider": "openai",
    "model_name": "gpt-3.5-turbo",
    "prompt_version": "1.0",
    "sampling_params": {
      "temperature": 0.3,
      "max_tokens": 500,
      "top_p": 1.0
    },
    "prompt_hash": "abc123...",
    "output_hash": "def456...",
    "output_summary": {...},
    "error": null,
    "fallback": false
  }
}
```

## 错误处理

- **Timeout**: 最多重试 2 次（仅 429 / 5xx 错误）
- **4xx 错误**: 不重试，直接 fallback
- **JSON 解析失败**: 使用 fallback
- **Schema 校验失败**: 使用 fallback

## 验证

运行测试脚本验证 LLM 集成：

```bash
python test_api.py
```

测试会验证：
- LLM 成功路径
- LLM 失败路径（API Key 无效时）
- 系统仍能完成执行
























