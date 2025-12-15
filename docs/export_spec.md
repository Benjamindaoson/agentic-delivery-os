# 导出与对比规格说明

> 本文档定义导出与对比的结构化规格

## 1. 导出包结构（强制）

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

---

## 2. 文件规格

### 2.1 trace_summary.json

来自 `TraceStore.load_summary(task_id)`：

```json
{
  "task_id": "uuid",
  "state": "COMPLETED",
  "current_plan_id": "normal_v1",
  "current_plan_path_type": "normal",
  "key_decisions_topk": [...],
  "cost_summary": {...},
  "result_summary": {...}
}
```

### 2.2 execution_plan.json

来自 `trace_data.execution_plan`：

```json
{
  "plan_id": "normal_v1",
  "plan_version": "1.0",
  "path_type": "normal",
  "plan_selection_history": [...],
  "executed_nodes": [...],
  "conditions_evidence": {...}
}
```

### 2.3 governance_decisions.json

来自 `trace_data.governance_decisions`：

```json
[
  {
    "execution_mode": "normal",
    "reasoning": "...",
    "conflicts": [...],
    "metrics": {...}
  }
]
```

### 2.4 summary.json

来自 `HierarchicalSummaryEngine.summarize()`：

```json
{
  "level_0": [
    {
      "text": "...",
      "evidence": {...}
    }
  ],
  "level_1": [...],
  "level_2": [...],
  "summary_version": "1.0",
  "summary_hash": "..."
}
```

### 2.5 narrative.json

来自 `NarrativeEngine.generate()`（每个 governance_decision）：

```json
[
  {
    "narrative_id": "DEGRADED_BUDGET",
    "text": "系统因预算超限自动降级执行",
    "narrative_version": "1.0",
    "narrative_hash": "..."
  }
]
```

### 2.6 cost_report.json

成本报告：

```json
{
  "actual_tokens": 11320,
  "actual_usd": 0.45,
  "delta_tokens": -680,
  "delta_usd": -0.03
}
```

### 2.7 manifest.json

导出清单：

```json
{
  "task_id": "uuid",
  "export_hash": "sha256(...)",
  "created_at": "2024-01-01T00:00:00",
  "files": [
    "trace_summary.json",
    "execution_plan.json",
    "governance_decisions.json",
    "summary.json",
    "narrative.json",
    "cost_report.json"
  ]
}
```

---

## 3. Hash 计算规则

### 3.1 export_hash

```python
all_content = ""
for file in files:
    with open(file) as f:
        all_content += f.read()
export_hash = hashlib.sha256(all_content.encode()).hexdigest()
```

### 3.2 验证方法

```python
def verify_export(export_dir):
    manifest_path = os.path.join(export_dir, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    all_content = ""
    for file in manifest["files"]:
        file_path = os.path.join(export_dir, file)
        with open(file_path) as f:
            all_content += f.read()
    
    calculated_hash = hashlib.sha256(all_content.encode()).hexdigest()
    assert calculated_hash == manifest["export_hash"]
```

---

## 4. 对比功能规格

### 4.1 对比输入

```
GET /api/expression/compare?task_id_a={id1}&task_id_b={id2}
```

### 4.2 对比输出

```json
{
  "task_id_a": "uuid1",
  "task_id_b": "uuid2",
  "path_differences": {
    "plan_a": ["normal_v1"],
    "plan_b": ["degraded_v1"]
  },
  "cost_differences": {
    "cost_a": 0.5,
    "cost_b": 0.3,
    "delta": -0.2
  },
  "failure_type_differences": {
    "failure_a": null,
    "failure_b": "data_issue"
  },
  "decision_differences": {
    "decisions_a": ["normal"],
    "decisions_b": ["degraded"]
  },
  "compare_version": "1.0",
  "compared_at": "2024-01-01T00:00:00"
}
```

### 4.3 对比规则（确定性）

1. **路径差异**：对比 `plan_selection_history`
2. **成本差异**：对比 `cost_impact` 累计
3. **失败类型差异**：对比 `evaluation_feedback_flow.last_failure_type`
4. **决策差异**：对比 `governance_decisions.execution_mode`

---

## 5. 脱敏规则

### 5.1 导出前脱敏

导出前必须应用脱敏策略（如果 role 不是 OWNER）：

```python
from runtime.platform.security import SecurityEngine, Role
security = SecurityEngine()
sanitized_trace = security.sanitize_trace(trace_data, role=Role.VIEWER)
```

### 5.2 敏感字段

- `prompt`
- `raw_prompt`
- `api_key`
- `secret`
- `password`
- `token`

脱敏后格式：`[REDACTED:{hash}]`

---

## 6. 验收标准

- ✅ 导出包结构完整
- ✅ 所有文件可读
- ✅ manifest.json 中的 export_hash 正确
- ✅ 对比功能可用
- ✅ 导出前应用脱敏（如适用）
- ✅ 所有文件结构化、可 hash

---

## 7. 实现位置

- `runtime/product/export.py`
- API: `GET /api/expression/{task_id}/export`
- API: `GET /api/expression/compare`

---

**状态**: ✅ **导出与对比规格已定义**


