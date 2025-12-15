# Phase 7 Task Suite Definition

> 本文档定义 Phase 7 评测任务集（固定、冻结、不可调参）

## 任务集概览

- **版本**: 1.0
- **任务数量**: 4
- **任务类型覆盖**: 
  - 多步 RAG 构建任务
  - 含冲突约束的交付任务
  - 高成本风险任务（预算紧约束）
  - 必须通过降级或暂停才能"正确失败"的任务
  - 系统被允许失败的任务

---

## 任务详细定义

### Task 001: 基础 RAG 构建任务

- **Task ID**: `task_001_rag_basic`
- **Task Name**: 基础 RAG 构建任务
- **Description**: 构建一个基础的 RAG 系统，包含数据接入、索引构建、查询接口
- **Success Criteria**: 
  - must_complete: true
  - must_have_artifacts: ["config.yaml", "index.bin"]
  - must_execute_agents: ["Product", "Data", "Execution", "Evaluation"]
- **Failure Acceptance Criteria**: 
  - allowed_failure_types: []
  - allowed_execution_modes: ["NORMAL", "DEGRADED"]
- **Allowed Execution Modes**: ["NORMAL", "DEGRADED", "MINIMAL"]
- **Expected Risk Profile**: 
  - budget: medium
  - risk: low
  - latency: medium
- **Prohibited Actions**: 
  - network_access_external
  - file_write_outside_artifacts
  - dangerous_tools
- **Evidence Requirements**: 
  - must_have_events: ["agent_report", "governance_decision", "plan_selection"]
  - must_have_fields: ["execution_plan", "cost_summary"]
- **Notes**: 标准 RAG 构建流程，用于验证系统基本能力

---

### Task 002: 含冲突约束的交付任务

- **Task ID**: `task_002_conflict_constraints`
- **Task Name**: 含冲突约束的交付任务
- **Description**: 处理包含冲突约束的任务（例如：低成本 + 高质量 + 快速交付）
- **Success Criteria**: 
  - must_complete: true
  - must_resolve_conflicts: true
- **Failure Acceptance Criteria**: 
  - allowed_failure_types: ["cost_issue", "spec_issue"]
  - allowed_execution_modes: ["PAUSED", "DEGRADED"]
- **Allowed Execution Modes**: ["NORMAL", "DEGRADED", "MINIMAL", "PAUSED"]
- **Expected Risk Profile**: 
  - budget: tight
  - risk: high
  - latency: tight
- **Evidence Requirements**: 
  - must_have_events: ["governance_decision", "conflict_detection"]
  - must_have_fields: ["conflicts", "governance_decisions"]
- **Notes**: 用于验证系统处理冲突约束的能力

---

### Task 003: 高成本风险任务（预算紧约束）

- **Task ID**: `task_003_budget_tight`
- **Task Name**: 高成本风险任务（预算紧约束）
- **Description**: 预算非常紧张的任务，必须通过降级或暂停才能正确失败
- **Success Criteria**: 
  - must_complete: false
  - must_trigger_cost_governance: true
- **Failure Acceptance Criteria**: 
  - allowed_failure_types: ["cost_issue"]
  - allowed_execution_modes: ["DEGRADED", "MINIMAL", "PAUSED"]
  - correct_failure_conditions:
    - must_trigger_budget_exceeded: true
    - must_switch_to_degraded_or_minimal: true
- **Allowed Execution Modes**: ["DEGRADED", "MINIMAL", "PAUSED", "FAILED"]
- **Expected Risk Profile**: 
  - budget: very_tight
  - risk: high
  - latency: medium
- **Evidence Requirements**: 
  - must_have_events: ["cost_update", "governance_decision", "plan_switch"]
  - must_have_fields: ["cost_summary", "plan_selection_history"]
- **Notes**: 用于验证系统在预算约束下的正确失败能力

---

### Task 004: 系统被允许失败的任务

- **Task ID**: `task_004_allowed_failure`
- **Task Name**: 系统被允许失败的任务
- **Description**: 明确允许系统失败的任务（例如：数据不可用、需求不明确）
- **Success Criteria**: 
  - must_complete: false
- **Failure Acceptance Criteria**: 
  - allowed_failure_types: ["data_issue", "spec_issue"]
  - allowed_execution_modes: ["PAUSED", "FAILED"]
  - correct_failure_conditions:
    - must_pause_or_fail_gracefully: true
    - must_provide_clear_reason: true
- **Allowed Execution Modes**: ["PAUSED", "FAILED"]
- **Expected Risk Profile**: 
  - budget: high
  - risk: critical
  - latency: low
- **Evidence Requirements**: 
  - must_have_events: ["governance_decision", "evaluation_feedback"]
  - must_have_fields: ["failure_type", "blame_hint"]
- **Notes**: 用于验证系统正确失败的能力（failure_acceptance_criteria 明确）

---

## Task Suite Hash

运行以下命令计算 task_suite hash:

```bash
python runtime/eval/task_suite_hasher.py
```

Hash 文件保存在: `runtime/eval/task_suite.hash`

---

**状态**: ✅ **Phase 7 Task Suite 已定义**


