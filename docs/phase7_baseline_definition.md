# Phase 7 Baseline Systems Definition

> 本文档定义 Phase 7 对照系统（Baseline Systems）

## 基线系统概览

- **版本**: 1.0
- **系统数量**: 4
- **系统类型**: 
  - naive_agent: 单 Agent，无治理
  - planner_executor: 有规划 + 执行，无成本治理
  - llm_heavy_agent: 高推理深度/多轮，高成本
  - full_system: 完整系统（我们的实现）

---

## 系统详细定义

### System 001: Naive Agent

- **System ID**: `naive_agent`
- **System Name**: Naive Agent
- **Description**: 单 Agent，无治理，无显式失败策略，无成本剪枝
- **Characteristics**:
  - agent_count: 1
  - has_governance: false
  - has_failure_strategy: false
  - has_cost_pruning: false
  - has_plan_selection: false
- **Implementation Path**: `runtime/baselines/naive_agent.py`
- **Version**: 1.0

---

### System 002: Planner Executor

- **System ID**: `planner_executor`
- **System Name**: Planner Executor
- **Description**: 有规划 + 执行，无成本治理，无失败回流闭环，无 conflict hard gate
- **Characteristics**:
  - agent_count: 2
  - has_governance: false
  - has_failure_strategy: false
  - has_cost_pruning: false
  - has_plan_selection: true
  - has_conflict_detection: false
- **Implementation Path**: `runtime/baselines/planner_executor.py`
- **Version**: 1.0

---

### System 003: LLM Heavy Agent

- **System ID**: `llm_heavy_agent`
- **System Name**: LLM Heavy Agent
- **Description**: 高推理深度/多轮，高成本，不限制失败路径，允许更聪明但不可控
- **Characteristics**:
  - agent_count: 1
  - has_governance: false
  - has_failure_strategy: false
  - has_cost_pruning: false
  - llm_usage: heavy
  - max_iterations: 10
- **Implementation Path**: `runtime/baselines/llm_heavy_agent.py`
- **Version**: 1.0

---

### System 004: Full System (Our Implementation)

- **System ID**: `full_system`
- **System Name**: Full System (Our Implementation)
- **Description**: 完整系统：多 Agent、治理、失败回流、成本剪枝、ExecutionPlan
- **Characteristics**:
  - agent_count: 6
  - has_governance: true
  - has_failure_strategy: true
  - has_cost_pruning: true
  - has_plan_selection: true
  - has_conflict_detection: true
  - has_evaluation_feedback_loop: true
- **Implementation Path**: `runtime/execution_graph/execution_engine.py`
- **Version**: 1.0

---

## Baseline 冻结约束

- ✅ 使用完全相同输入（同 `fixed_input_hash`）
- ✅ 禁止人为调参"补救失败"
- ✅ 禁止对单个任务单独改 prompt/config
- ✅ baseline 的失败不需要"合理"，但必须如实记录

---

## System Matrix Hash

运行以下命令计算 system_matrix hash:

```bash
python runtime/eval/system_matrix_hasher.py
```

Hash 文件保存在: `runtime/eval/system_matrix.hash`

---

**状态**: ✅ **Phase 7 Baseline Systems 已定义**


