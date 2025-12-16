# LLM Provider 配置指南

## Provider-Agnostic 架构

系统实现了统一的 LLM 接口，支持多个 Provider：
- **Qwen** (默认): 成本更低，适合工程验证
- **OpenAI**: OpenAI 兼容接口

## 配置方式

### 方式 1: 配置文件

编辑 `configs/system.yaml`:

```yaml
llm:
  provider: qwen  # qwen | openai
  model: qwen-turbo
  timeout_sec: 20
  max_retries: 2
  temperature: 0.0
  max_tokens: 512
  top_p: 1.0
```

### 方式 2: 环境变量

```bash
# Provider 选择
export LLM_PROVIDER=qwen  # 或 openai

# Qwen 配置
export QWEN_API_KEY=your_qwen_key
export QWEN_MODEL=qwen-turbo
export QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# OpenAI 配置
export OPENAI_API_KEY=your_openai_key
export OPENAI_MODEL=gpt-3.5-turbo
export OPENAI_BASE_URL=https://api.openai.com/v1
```

## 切换 Provider

只需修改 `LLM_PROVIDER` 环境变量或配置文件：

```bash
# 切换到 OpenAI
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key

# 切换回 Qwen
export LLM_PROVIDER=qwen
export QWEN_API_KEY=your_key
```

## 无 LLM 运行

如果未设置 API Key，系统会自动使用 fallback：
- Agent 的 decision 仍由工程规则决定
- reason 使用默认文本
- 系统仍能正常完成执行

## 验证

运行测试脚本：

```bash
python test_llm_integration.py
```

测试会验证：
- LLM 成功时，reason 包含 LLM 生成的内容
- LLM 失败时，系统仍能完成执行
- 多次执行不冲突




