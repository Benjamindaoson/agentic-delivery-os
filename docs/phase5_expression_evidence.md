# Phase 5 表达层实现证据

> 本文档提供 Phase 5 表达层的实现证据与验证方法

## 1. 实现文件清单

### 1.1 核心模块

- ✅ `runtime/expression/__init__.py` - 表达层初始化
- ✅ `runtime/expression/salience.py` - 显著性排序引擎
- ✅ `runtime/expression/summary.py` - 分层摘要引擎
- ✅ `runtime/expression/narrative.py` - 叙事引擎（确定映射）

### 1.2 产品层模块

- ✅ `runtime/product/cost_accounting.py` - 成本核算引擎
- ✅ `runtime/product/export.py` - 导出与对比引擎

### 1.3 API 端点

- ✅ `backend/api/expression.py` - 表达层 API
- ✅ 已集成到 `backend/main.py`

---

## 2. 确定性验证方法

### 2.1 Salience 确定性验证

```python
# 测试：同输入必得同输出
input_data = SalienceInput(task_id="test", events=[...])
engine = SalienceEngine()
output1 = engine.rank(input_data)
output2 = engine.rank(input_data)
assert output1.ranked_event_ids == output2.ranked_event_ids
assert output1.salience_hash == output2.salience_hash
```

### 2.2 Summary 确定性验证

```python
# 测试：同 trace 必得同 hash
trace_data = {...}
engine = HierarchicalSummaryEngine()
output1 = engine.summarize(trace_data)
output2 = engine.summarize(trace_data)
assert output1.summary_hash == output2.summary_hash
```

### 2.3 Narrative 确定性验证

```python
# 测试：同输入必得同输出
input_data = NarrativeInput(governance_decision="degraded", trigger="BUDGET_EXCEEDED")
engine = NarrativeEngine()
output1 = engine.generate(input_data)
output2 = engine.generate(input_data)
assert output1.narrative_id == output2.narrative_id
assert output1.narrative_hash == output2.narrative_hash
```

### 2.4 无默认分支验证

```python
# 测试：无匹配模板必须失败
input_data = NarrativeInput(governance_decision="unknown", trigger="unknown")
engine = NarrativeEngine()
try:
    engine.generate(input_data)
    assert False, "Should raise ValueError"
except ValueError:
    pass  # 正确行为
```

---

## 3. 证据绑定验证

### 3.1 Summary 证据绑定

每个 summary_item 必须包含：

```json
{
  "text": "...",
  "evidence": {
    "event_id": "...",
    "trace_offset": "...",
    "type": "..."
  }
}
```

验证方法：检查所有 summary_item 的 evidence 字段是否非空。

### 3.2 Narrative 模板匹配

每个 narrative 必须来自模板：

```json
{
  "narrative_id": "DEGRADED_BUDGET",
  "text": "系统因预算超限自动降级执行",
  "narrative_version": "1.0",
  "narrative_hash": "..."
}
```

验证方法：检查 narrative_id 是否在模板列表中。

---

## 4. Hash 验证

### 4.1 Hash 计算规则

所有 hash 计算使用 SHA256，输入包括：
- 输入数据（JSON，sort_keys=True）
- 输出数据（JSON，sort_keys=True）
- 版本号

### 4.2 Hash 验证方法

```python
import hashlib
import json

def verify_hash(data, version, expected_hash):
    data_json = json.dumps(data, sort_keys=True)
    combined = data_json + version
    calculated_hash = hashlib.sha256(combined.encode()).hexdigest()
    return calculated_hash == expected_hash
```

---

## 5. 成本预测与核算验证

### 5.1 预测规则验证

预测基于确定性规则：
- spec_length → base_tokens
- node_count → node_tokens
- retry_count → retry_multiplier
- path_type → success_proxy

验证方法：检查 forecast_evidence 中的 calculation_steps。

### 5.2 核算验证

核算从 trace 提取：
- actual_tokens: 从 agent_reports 累计
- actual_usd: 基于 tokens 计算
- evidence_events: 成本相关事件

验证方法：检查 evidence_events 是否指向真实事件。

### 5.3 偏差解释验证

偏差解释基于确定性规则：
- 重试 → increased_cost
- 降级 → reduced_cost
- 工具调用 → increased_cost

验证方法：检查 explanation_items 是否基于 trace 证据。

---

## 6. 导出包验证

### 6.1 文件完整性

导出包必须包含：
- trace_summary.json
- execution_plan.json
- governance_decisions.json
- summary.json
- narrative.json
- cost_report.json
- manifest.json

验证方法：检查 manifest.json 中的 files 列表。

### 6.2 Hash 验证

manifest.json 中的 export_hash 必须等于所有文件内容的 SHA256。

验证方法：
```python
all_content = ""
for file in manifest["files"]:
    with open(file) as f:
        all_content += f.read()
calculated_hash = hashlib.sha256(all_content.encode()).hexdigest()
assert calculated_hash == manifest["export_hash"]
```

---

## 7. 对比功能验证

### 7.1 对比规则

对比基于确定性规则：
- 路径差异：plan_selection_history 对比
- 成本差异：cost_impact 累计对比
- 失败类型差异：evaluation_feedback_flow 对比
- 决策差异：governance_decisions 对比

验证方法：检查对比输出是否基于 trace 数据。

---

## 8. 系统约束保持验证

### 8.1 无 LLM 参与

验证方法：grep 代码库，确认表达层模块无 LLM 调用。

### 8.2 无自由文本生成

验证方法：检查所有文本输出是否来自模板或确定性规则。

### 8.3 证据绑定

验证方法：检查所有表达输出是否包含 evidence 或可追溯的 trace_offset。

---

## 9. 性能验证

### 9.1 大 trace 场景

测试方法：
- 生成包含 1000+ 事件的 trace
- 测试 summary 生成时间 < 1秒
- 测试 salience 排序时间 < 0.5秒

---

## 10. 完成判定

Phase 5 表达层完成当且仅当：

- ✅ 所有模块实现完成
- ✅ 所有确定性验证通过
- ✅ 所有证据绑定验证通过
- ✅ 所有 hash 验证通过
- ✅ 无 LLM 参与
- ✅ 无自由文本生成
- ✅ 无默认分支
- ✅ 导出包可完整回放任务

---

**状态**: ✅ **Phase 5 表达层实现证据已记录**


