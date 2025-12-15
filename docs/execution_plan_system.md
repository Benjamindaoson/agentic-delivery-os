# ExecutionPlan 系统说明

## 概述

系统已实现显式、可审计的执行计划系统（ExecutionPlan），将执行路径从"写死顺序"升级为"条件 DAG"。

## 核心组件

### 1. ExecutionPlan（执行计划）

显式对象化的执行图，包含：
- **plan_id**: 计划标识
- **plan_version**: 计划版本
- **path_type**: 路径类型（NORMAL / DEGRADED / MINIMAL）
- **nodes**: 节点列表（条件 DAG）
- **description**: 计划描述

### 2. PlanNode（计划节点）

每个节点包含：
- **node_id**: 节点标识
- **agent_name**: 对应的 Agent
- **condition**: 节点条件（决定是否执行）
- **required**: 是否必需
- **cost_estimate**: 成本估算
- **risk_level**: 风险级别

### 3. NodeCondition（节点条件）

支持的条件类型：
- **always**: 总是执行
- **budget_check**: 预算检查（budget_remaining > threshold）
- **risk_check**: 风险检查（risk_level 不在 high/critical）
- **evaluation_feedback**: Evaluation 信号回流（基于上次失败类型）

### 4. PlanSelector（计划选择器）

规则驱动的计划选择（非学习型、可静态审计）：

**选择规则（优先级从高到低）**：
1. Governance mode == PAUSED → 不选择计划
2. Governance mode == MINIMAL → MINIMAL 计划
3. Governance mode == DEGRADED → DEGRADED 计划
4. 预算受限（budget_remaining < 100）→ DEGRADED 计划
5. Evaluation 反馈上次数据问题 → DEGRADED 计划（跳过数据节点）
6. 默认 → NORMAL 计划

所有规则都是静态的、可审计的、非学习型的。

## 三条执行路径

### NORMAL 路径
完整交付路径：Product → Cost → Data → Cost → Execution → Cost → Evaluation

### DEGRADED 路径
降级路径：Product → Cost → Data（条件执行）→ Execution（最小功能）→ Evaluation

### MINIMAL 路径
最小可行路径：Product → Execution → Evaluation

## 成本预算触发路径剪枝

系统在以下情况触发路径切换：
1. **预算超限**：budget_remaining < 0 → 切换到 DEGRADED
2. **治理决策**：Governance 决策为 DEGRADED/MINIMAL → 切换计划
3. **动态切换**：执行过程中检测到预算不足 → 重新选择计划

路径切换会：
- 记录到 `plan_selection_history`
- 重新获取可执行节点
- 继续执行新计划

## Evaluation → 调度回流闭环

Evaluation Agent 输出结构化信号：
- `failure_type`: 失败类型（如 "data_issue"）
- `blame_hint`: 归因线索（如 "Data Agent"）

这些信号会：
1. 写入 `state_update`（`last_evaluation_failed`, `last_failure_type`, `last_blame_hint`）
2. 在下一次执行时被读取
3. 影响计划选择（如果上次数据问题，选择 DEGRADED 计划跳过数据节点）

## Trace 记录

`system_trace.json` 包含完整的 ExecutionPlan 信息：

```json
{
  "execution_plan": {
    "plan_id": "normal_v1",
    "plan_version": "1.0",
    "path_type": "normal",
    "plan_selection_history": [
      {
        "selected_plan_id": "normal_v1",
        "reasoning": "Governance mode: normal",
        "signals_used": {...}
      }
    ],
    "executed_nodes": [...],
    "conditions_evidence": {
      "Product": {
        "budget_remaining": 1000.0,
        "risk_level": "low",
        "confidence": 1.0
      }
    }
  }
}
```

## 可审计性

系统可通过 trace 回答：
1. **为什么选择这个计划？** → 查看 `plan_selection_history`
2. **为什么执行这些节点？** → 查看 `executed_nodes` 和 `conditions_evidence`
3. **为什么切换计划？** → 查看 `plan_selection_history` 中的 `trigger`
4. **条件如何命中？** → 查看 `conditions_evidence`

## 系统约束保持

- ✅ 状态流转逻辑未改变
- ✅ Agent 接口未改变
- ✅ 执行顺序由计划决定，但语义保持一致
- ✅ 计划选择完全规则驱动，非学习型


