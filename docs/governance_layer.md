# 治理层说明

## 概述

系统已引入治理层与可解释层，确保系统在复杂、冲突、失败、预算受限场景下仍然可控、可解释、可审计。

## 核心组件

### 1. Agent Execution Report（Agent 执行报告）

将 Agent 输出信号化，包含：
- **decision**: Agent 决策
- **status**: 执行状态（success / warning / error / skipped）
- **confidence**: 置信度（0.0 - 1.0）
- **risk_level**: 风险级别（low / medium / high / critical）
- **cost_impact**: 成本影响
- **signals**: 结构化信号
- **conflicts**: 与其他 Agent 的冲突
- **llm_fallback_used**: LLM fallback 使用情况

### 2. Conflict Detector（冲突检测器）

检测 Agent 之间的分歧：
- **决策冲突**: Product vs Evaluation 决策不一致
- **置信度冲突**: 多个 Agent 置信度低
- **风险级别冲突**: 高风险 Agent 聚集
- **成本信号冲突**: 预算警告

冲突严重性：
- **SOFT**: 可容忍的不一致
- **HARD**: 必须处理的不一致

### 3. Governance Engine（治理引擎）

基于规则进行系统级决策：

**决策规则（优先级从高到低）**：
1. 硬冲突 → PAUSED（暂停等待人工介入）
2. 预算超限 → DEGRADED（降级执行）
3. 高风险 + 低置信度 → PAUSED
4. 多个 LLM fallback → DEGRADED
5. 软冲突 → MINIMAL（最小执行）
6. 其他 → NORMAL（正常执行）

**执行模式**：
- **NORMAL**: 正常执行
- **DEGRADED**: 降级执行（使用最小功能）
- **MINIMAL**: 最小执行（仅核心功能）
- **PAUSED**: 暂停等待人工介入

## 治理检查点

系统在以下关键阶段插入治理检查点：
1. **after_product**: Product Agent 执行后
2. **after_data**: Data Agent 执行后
3. **after_execution**: Execution Agent 执行后
4. **after_evaluation**: Evaluation Agent 执行后（最终检查）

每个检查点：
1. 汇总 Agent 信号
2. 检测冲突
3. 执行治理规则
4. 记录可审计决策

## Trace 增强

`system_trace.json` 新增字段：
- **agent_reports**: 所有 Agent 的结构化报告
- **governance_decisions**: 所有治理决策记录

每个治理决策包含：
- **execution_mode**: 执行模式
- **restrictions**: 限制条件
- **reasoning**: 系统级理由（非 Agent 理由）
- **conflicts**: 检测到的冲突
- **metrics**: 系统指标（平均置信度、风险计数、成本等）
- **checkpoint**: 检查点名称

## 可解释性

系统可通过 trace 回答以下问题：

1. **是否存在 Agent 分歧？为什么？**
   - 查看 `governance_decisions` 中的 `conflicts` 字段

2. **系统为何选择继续 / 降级 / 暂停？**
   - 查看 `governance_decisions` 中的 `execution_mode` 和 `reasoning`

3. **是否触发预算或风险规则？**
   - 查看 `governance_decisions` 中的 `metrics` 字段

4. **若 LLM 失败，系统如何保持稳定？**
   - 查看 `agent_reports` 中的 `llm_fallback_used` 和治理决策

5. **不同任务下系统行为是否一致、可复现？**
   - 对比不同任务的 `governance_decisions` 和 `agent_reports`

## 系统约束保持

- ✅ 状态流转逻辑未改变：IDLE → SPEC_READY → RUNNING → COMPLETED / FAILED
- ✅ StateManager / ExecutionEngine 职责未改变
- ✅ Agent.execute(context, task_id) 接口签名未改变
- ✅ 执行顺序未改变
- ✅ 治理层失败不影响系统完成（返回默认 NORMAL 决策）

## 验证

运行测试脚本验证治理层：

```bash
python test_api.py
```

检查 `artifacts/rag_project/{task_id}/system_trace.json` 中的：
- `agent_reports`: 验证 Agent 信号化
- `governance_decisions`: 验证治理决策记录
- `conflicts`: 验证冲突检测


