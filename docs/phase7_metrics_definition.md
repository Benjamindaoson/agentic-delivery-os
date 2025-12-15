# Phase 7 Metrics Definition

> 本文档定义 Phase 7 评测指标（不可狡辩指标）

## 指标概览

所有指标必须：
- ✅ 基于 trace / artifacts 计算
- ✅ 可复现
- ✅ 可审计
- ✅ 不依赖主观判断
- ✅ 每个指标必须有：定义、公式、字段来源、缺失时的处理规则

---

## 指标详细定义

### Metric 001: Task Completion Rate

- **Metric ID**: `task_completion_rate`
- **Metric Name**: Task Completion Rate
- **Definition**: 完成任务的比例
- **Formula**: `completed_tasks / total_tasks`
- **Field Source**: `execution_result.status == 'COMPLETED'`
- **Missing Handling**: count as failed
- **Unit**: ratio
- **Range**: [0.0, 1.0]

---

### Metric 002: Correct Failure Rate

- **Metric ID**: `correct_failure_rate`
- **Metric Name**: Correct Failure Rate
- **Definition**: 符合 failure_acceptance_criteria 的失败比例
- **Formula**: `correct_failures / total_failures`
- **Field Source**: `case_result.correct_failure == true`
- **Missing Handling**: count as incorrect failure
- **Unit**: ratio
- **Range**: [0.0, 1.0]

---

### Metric 003: Cost per Successful Task

- **Metric ID**: `cost_per_successful_task`
- **Metric Name**: Cost per Successful Task
- **Definition**: 每个成功任务的平均成本
- **Formula**: `sum(cost for completed) / count(completed)`
- **Field Source**: `case_result.cost where status == 'COMPLETED'`
- **Missing Handling**: exclude from calculation
- **Unit**: USD
- **Range**: [0.0, null]

---

### Metric 004: Cost Wasted on Failed Paths

- **Metric ID**: `cost_wasted_on_failed_paths`
- **Metric Name**: Cost Wasted on Failed Paths
- **Definition**: 失败路径浪费的成本
- **Formula**: `sum(cost for failed and incorrect_failure)`
- **Field Source**: `case_result.cost where status != 'COMPLETED' and correct_failure == false`
- **Missing Handling**: count as wasted
- **Unit**: USD
- **Range**: [0.0, null]

---

### Metric 005: Recovery Success Rate

- **Metric ID**: `recovery_success_rate`
- **Metric Name**: Recovery Success Rate
- **Definition**: 从失败中恢复成功的比例
- **Formula**: `recovered_tasks / failed_tasks`
- **Field Source**: `trace.governance_decisions with execution_mode change`
- **Missing Handling**: count as no recovery
- **Unit**: ratio
- **Range**: [0.0, 1.0]

---

### Metric 006: Mean Replay Length

- **Metric ID**: `mean_replay_length`
- **Metric Name**: Mean Replay Length
- **Definition**: 平均回放长度（事件数量）
- **Formula**: `sum(replay_length) / count(tasks)`
- **Field Source**: `replay_view.total_events`
- **Missing Handling**: use 0
- **Unit**: events
- **Range**: [0, null]

---

## Metrics Registry Hash

运行以下命令计算 metrics_registry hash:

```bash
python runtime/eval/metrics_registry_hasher.py
```

Hash 文件保存在: `runtime/eval/metrics_registry.hash`

---

**状态**: ✅ **Phase 7 Metrics Definition 已定义**


