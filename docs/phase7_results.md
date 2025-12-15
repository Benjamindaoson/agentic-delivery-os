# Phase 7 Results

> 本文档展示 Phase 7 评测结果（只允许结构化，不允许叙事）

## 结果概览

- **Run ID**: 见 `artifacts/phase7/runs/` 目录
- **Task Suite**: 见 `docs/phase7_task_suite.md`
- **System Matrix**: 见 `docs/phase7_baseline_definition.md`
- **Metrics**: 见 `docs/phase7_metrics_definition.md`

---

## Leaderboard

### 汇总结果（JSON）

见: `artifacts/phase7/summary/leaderboard_{run_id}.json`

### 汇总结果（CSV）

见: `artifacts/phase7/summary/leaderboard_{run_id}.csv`

### 字段说明

- `system_id`: 系统标识
- `total_tasks`: 总任务数
- `completed`: 完成任务数
- `failed`: 失败任务数
- `correct_failures`: 正确失败数
- `total_cost`: 总成本
- `cost_per_success`: 每个成功任务的平均成本
- `mean_replay_length`: 平均回放长度

---

## Case 详情

每个 case 的完整证据包位于:

`artifacts/phase7/cases/{task_id}/{system_id}/`

包含文件：
- `input_snapshot.json`
- `input_hash.txt`
- `run_metadata.json`
- `trace_export.json`
- `replay_view.json`
- `cost_outcome.json`
- `failure_explain.json` (如适用)
- `metrics.json`
- `export_audit_pack.zip`
- `case_hash.txt`

---

## 证据引用

所有结果均可通过以下方式引用：

- **Case**: `artifacts/phase7/cases/{task_id}/{system_id}/`
- **Run**: `artifacts/phase7/runs/{run_id}/`
- **Summary**: `artifacts/phase7/summary/leaderboard_{run_id}.json`

---

## 运行方法

运行评测：

```bash
python scripts/run_phase7_evaluation.py
```

---

**状态**: ✅ **Phase 7 Results 模板已定义**

**注意**: 实际结果需运行评测后生成，本文档仅提供结构模板。


