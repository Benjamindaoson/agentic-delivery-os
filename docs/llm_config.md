# LLM 配置说明

## 环境变量

系统通过环境变量配置 LLM Provider：

```bash
# LLM Provider (openai / anthropic / azure_openai)
export LLM_PROVIDER=openai

# API Key (必需)
export LLM_API_KEY=your_api_key_here

# Model Name (默认: gpt-3.5-turbo)
export LLM_MODEL=gpt-3.5-turbo

# Base URL (仅 Azure OpenAI 需要)
export LLM_BASE_URL=https://your-resource.openai.azure.com
```

## 无 LLM 运行

如果未设置 `LLM_API_KEY` 或 LLM 调用失败，系统会自动使用 fallback：
- Agent 的 decision 仍由工程规则决定
- reason 使用默认文本
- 系统仍能正常完成执行

## 验证配置

运行测试脚本验证 LLM 配置：

```bash
# 设置环境变量
export LLM_API_KEY=your_key

# 运行测试
python test_api.py
```

测试会验证：
- LLM 成功时，reason 包含 LLM 生成的内容
- LLM 失败时，系统仍能完成执行
























