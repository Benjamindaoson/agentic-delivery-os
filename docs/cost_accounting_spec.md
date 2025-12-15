# 成本预测与计量规格说明

> 本文档定义成本预测与计量的确定性规则与实现规格

## 1. 总原则

- **成本预测 = 确定性规则，非学习**
- **成本核算 = 基于 trace 证据**
- **偏差解释 = 确定性规则**
- **所有计算可审计、可复现**

---

## 2. 执行前预测

### 2.1 输入特征（确定性）

- `spec_length`: spec 长度（字符数）
- `node_count`: 节点数
- `tool_call_count`: 工具调用数
- `retry_count`: 历史重试数
- `path_type`: 路径类型（NORMAL/DEGRADED/MINIMAL）

### 2.2 预测规则（确定性）

1. **基础 token 估算**
   ```
   base_tokens = spec_length * token_per_char (0.25)
   ```

2. **节点 token 估算**
   ```
   node_tokens = node_count * node_tokens_per_node
   node_tokens_per_node = {
     NORMAL: 2000,
     DEGRADED: 1500,
     MINIMAL: 1000
   }
   ```

3. **重试增加成本**
   ```
   retry_multiplier = 1.0 + (retry_count * 0.1)
   total_tokens = (base_tokens + node_tokens) * retry_multiplier
   ```

4. **工具调用增加成本**
   ```
   tool_tokens = tool_call_count * 100
   total_tokens += tool_tokens
   ```

5. **计算区间（±20%）**
   ```
   tokens_min = total_tokens * 0.8
   tokens_max = total_tokens * 1.2
   ```

6. **转换为 USD**
   ```
   usd_min = (tokens_min / 1000) * usd_per_1k_tokens (0.002)
   usd_max = (tokens_max / 1000) * usd_per_1k_tokens
   ```

### 2.3 输出规格

```json
{
  "predicted_tokens": 12000,
  "predicted_usd": 0.48,
  "prediction_version": "1.0",
  "prediction_hash": "sha256(...)"
}
```

### 2.4 实现位置

- `runtime/optimization/cost_forecaster.py`
- `runtime/product/cost_accounting.py`
- API: `GET /api/expression/{task_id}/cost/predict`

---

## 3. 执行后核算

### 3.1 核算规则（确定性）

1. **提取实际 tokens**
   ```
   actual_tokens = sum(
     agent_report.signals.tokens_used
     for agent_report in trace.agent_reports
   )
   ```

2. **计算实际 USD**
   ```
   actual_usd = (actual_tokens / 1000) * usd_per_1k_tokens
   ```

3. **计算偏差**
   ```
   delta_tokens = actual_tokens - predicted_tokens
   delta_usd = actual_usd - predicted_usd
   ```

4. **提取证据事件**
   ```
   evidence_events = [
     f"agent_report_{i}"
     for i, report in enumerate(agent_reports)
     if report.cost_impact > 0
   ]
   ```

### 3.2 输出规格

```json
{
  "actual_tokens": 11320,
  "actual_usd": 0.45,
  "delta_tokens": -680,
  "delta_usd": -0.03,
  "evidence_events": ["agent_report_1", "agent_report_9"],
  "accounting_version": "1.0",
  "accounting_hash": "sha256(...)"
}
```

---

## 4. 偏差解释（确定性规则）

### 4.1 解释规则

1. **重试增加成本**
   ```
   if retry_count > 0:
     explanation_items.append({
       "reason": "LLM fallback retries",
       "count": retry_count,
       "impact": "increased_cost"
     })
   ```

2. **降级可能降低成本**
   ```
   if has_degraded and delta_type == "under":
     explanation_items.append({
       "reason": "Execution degraded",
       "impact": "reduced_cost"
     })
   ```

3. **工具调用增加成本**
   ```
   if tool_count > 0:
     explanation_items.append({
       "reason": "Tool executions",
       "count": tool_count,
       "impact": "increased_cost" if delta_type == "over" else "reduced_cost"
     })
   ```

### 4.2 输出规格

```json
{
  "delta_type": "under",
  "delta_amount": 0.03,
  "explanation_items": [
    {
      "reason": "Execution degraded",
      "impact": "reduced_cost"
    }
  ],
  "explanation_version": "1.0"
}
```

---

## 5. 可审计性

### 5.1 预测证据

预测必须包含 `forecast_evidence`：

```json
{
  "forecaster_version": "1.0",
  "input_features": {...},
  "calculation_steps": {
    "base_tokens": 1000,
    "node_tokens_per_node": 2000,
    "total_node_tokens": 10000,
    "retry_multiplier": 1.1,
    "tool_tokens": 500,
    "total_tokens_base": 11500,
    "tokens_range": [9200, 13800],
    "latency_base": 50.0,
    "latency_range": [40.0, 60.0]
  }
}
```

### 5.2 核算证据

核算必须包含 `evidence_events`，指向 trace 中的真实事件。

---

## 6. 验收标准

- ✅ 预测基于确定性规则（非学习）
- ✅ 核算基于 trace 证据
- ✅ 偏差有证据解释
- ✅ 所有计算可审计
- ✅ 预测与核算可对账
- ✅ 有版本号和 hash

---

**状态**: ✅ **成本预测与计量规格已定义**


