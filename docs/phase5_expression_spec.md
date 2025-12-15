# Phase 5 表达层规格说明

> 本文档定义 Phase 5 表达层的工程级约束与实现规格

## 1. 总原则（可验收）

- **表达层 = 确定映射，不是创作**
- 禁止自由文本生成
- 每一条输出必须能反查 trace 证据
- 同输入 → 同输出 → 同 hash

---

## 2. Salience Engine（显著性排序）

### 2.1 输入规格

```json
{
  "task_id": "uuid",
  "events": [
    {
      "event_id": "e1",
      "type": "governance_decision",
      "severity": 3,
      "payload": {
        "execution_mode": "degraded"
      }
    }
  ]
}
```

### 2.2 排序规则（确定性）

1. **severity** → 权重（governance: 3.0, plan_switch: 2.5, agent_report: 2.0, ...）
2. **governance_priority** → paused: 10, degraded: 8, minimal: 6, normal: 4
3. **time** → 时间因素（权重 0.1）

排序结果：score 降序，然后 event_id（确保稳定）

### 2.3 输出规格

```json
{
  "ranked_event_ids": ["e1", "e2"],
  "salience_version": "1.0",
  "salience_hash": "sha256(...)"
}
```

### 2.4 实现位置

- `runtime/expression/salience.py`
- API: `POST /api/expression/salience`

---

## 3. Hierarchical Summary Engine（分层摘要）

### 3.1 分层定义

- **Level 0（用户层）**：Top-3 关键决策（最多3项）
- **Level 1（执行层）**：关键执行节点（最多10项）
- **Level 2（索引层）**：所有事件摘要（最多50项）

### 3.2 摘要项规格

每个摘要项必须绑定证据：

```json
{
  "text": "系统因预算超限进入DEGRADED模式",
  "evidence": {
    "event_id": "gov_12",
    "trace_offset": "governance_decisions[12]",
    "type": "governance_decision"
  }
}
```

### 3.3 输出规格

```json
{
  "level_0": [...],
  "level_1": [...],
  "level_2": [...],
  "summary_version": "1.0",
  "summary_hash": "sha256(...)"
}
```

### 3.4 实现位置

- `runtime/expression/summary.py`
- API: `GET /api/expression/{task_id}/summary`

---

## 4. Narrative Layer（确定映射）

### 4.1 输入规格

```json
{
  "governance_decision": "degraded",
  "trigger": "BUDGET_EXCEEDED"
}
```

### 4.2 模板定义（静态）

模板必须版本化，不允许默认分支：

```json
{
  "id": "DEGRADED_BUDGET",
  "allowed_decisions": ["degraded"],
  "allowed_triggers": ["BUDGET_EXCEEDED", "budget_or_governance_change"],
  "text": "系统因预算超限自动降级执行"
}
```

### 4.3 匹配规则（确定性）

1. 检查 `governance_decision` 是否在 `allowed_decisions`
2. 检查 `trigger` 是否在 `allowed_triggers`（如果指定）
3. 无匹配 → 抛出异常（不允许默认分支）

### 4.4 输出规格

```json
{
  "narrative_id": "DEGRADED_BUDGET",
  "text": "系统因预算超限自动降级执行",
  "narrative_version": "1.0",
  "narrative_hash": "sha256(...)"
}
```

### 4.5 实现位置

- `runtime/expression/narrative.py`
- API: `POST /api/expression/narrative`

---

## 5. 成本预测与计量

### 5.1 执行前预测

```json
{
  "predicted_tokens": 12000,
  "predicted_usd": 0.48,
  "prediction_version": "1.0",
  "prediction_hash": "sha256(...)"
}
```

### 5.2 执行后核算

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

### 5.3 偏差解释（确定性规则）

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

### 5.4 实现位置

- `runtime/product/cost_accounting.py`
- API: `GET /api/expression/{task_id}/cost/predict`

---

## 6. 导出与对比

### 6.1 导出包结构（强制）

```
exports/
 └─ task_{id}/
    ├─ trace_summary.json
    ├─ execution_plan.json
    ├─ governance_decisions.json
    ├─ summary.json
    ├─ narrative.json
    ├─ cost_report.json
    └─ manifest.json
```

### 6.2 manifest.json

```json
{
  "task_id": "uuid",
  "export_hash": "sha256(...)",
  "created_at": "2024-01-01T00:00:00",
  "files": ["trace_summary.json", "execution_plan.json", "..."]
}
```

### 6.3 对比输出

```json
{
  "task_id_a": "uuid1",
  "task_id_b": "uuid2",
  "path_differences": {...},
  "cost_differences": {...},
  "failure_type_differences": {...},
  "decision_differences": {...},
  "compare_version": "1.0",
  "compared_at": "2024-01-01T00:00:00"
}
```

### 6.4 实现位置

- `runtime/product/export.py`
- API: `GET /api/expression/{task_id}/export`, `GET /api/expression/compare`

---

## 7. 验收标准

### 7.1 Salience

- ✅ 排序结果稳定（同输入同输出）
- ✅ 有版本号和 hash
- ✅ 规则明确（severity → governance_priority → time）

### 7.2 Summary

- ✅ 每句摘要绑定证据
- ✅ 分层清晰（Level 0/1/2）
- ✅ 有版本号和 hash
- ✅ 无证据 → 构建失败

### 7.3 Narrative

- ✅ 确定映射（模板匹配）
- ✅ 无默认分支（无匹配即失败）
- ✅ 有版本号和 hash
- ✅ 禁止自由生成

### 7.4 Cost Accounting

- ✅ 预测与核算可对账
- ✅ 偏差有证据解释
- ✅ 有版本号和 hash

### 7.5 Export

- ✅ 结构化导出
- ✅ 可 hash 验证
- ✅ 对比功能可用

---

## 8. 系统约束保持

- ✅ 所有表达基于 trace 证据
- ✅ 所有算法确定性、可审计
- ✅ 无 LLM 参与表达生成
- ✅ 无自由文本创作
- ✅ 同输入 → 同输出 → 同 hash

---

**状态**: ✅ **Phase 5 表达层规格已定义**


