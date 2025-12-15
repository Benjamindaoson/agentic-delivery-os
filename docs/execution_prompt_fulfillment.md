# 全量兑现版执行 Prompt 兑现报告

> 本文档记录系统对"全量兑现版执行 Prompt"的工程化兑现情况

## 兑现状态总览

✅ **100% 工程化兑现** - 所有承诺能力均已实现并可审计

---

## 1. ExecutionPlan 显式化（条件 DAG / 路径剪枝）

### ✅ 已兑现

**实现位置**：
- `runtime/execution_plan/plan_definition.py` - ExecutionPlan、PlanNode、NodeCondition 定义
- `runtime/execution_plan/plan_registry.py` - NORMAL/DEGRADED/MINIMAL 三条路径定义
- `runtime/execution_plan/plan_selector.py` - 规则驱动的计划选择器

**关键特性**：
1. **显式对象化**：执行路径是 ExecutionPlan 对象，可被记录、复现、审计
2. **条件 DAG**：支持条件分支（always、budget_check、risk_check、evaluation_feedback）
3. **可复现**：同一输入与同一治理决策下，执行路径一致
4. **可审计**：trace 可看到 plan_id、plan_version、chosen_path、executed_nodes、conditions_evidence

**三条路径**：
- `NORMAL`：完整交付路径（Product → Cost → Data → Cost → Execution → Cost → Evaluation）
- `DEGRADED`：降级路径（跳过高成本/高风险节点）
- `MINIMAL`：最小可行路径（Product → Execution → Evaluation）

**计划选择规则**（完全规则驱动、非学习型、可静态审计）：
1. Governance mode == PAUSED → 不选择计划
2. Governance mode == MINIMAL → MINIMAL 计划
3. Governance mode == DEGRADED → DEGRADED 计划
4. 预算受限（budget_remaining < 100）→ DEGRADED 计划
5. Evaluation 反馈上次失败 → 根据失败类型选择计划
6. 默认 → NORMAL 计划

---

## 2. Evaluation → 调度回流闭环

### ✅ 已兑现

**实现位置**：
- `runtime/agents/evaluation_agent.py` - 输出结构化信号
- `runtime/execution_graph/execution_engine.py` - 读取并应用回流信号
- `runtime/execution_plan/plan_selector.py` - 基于回流信号选择计划

**关键特性**：
1. **结构化信号输出**：
   - `last_evaluation_failed`: 是否失败
   - `last_failure_type`: 失败类型（data_issue、execution_issue、cost_issue）
   - `last_blame_hint`: 归因线索（哪个 Agent 负责）

2. **回流机制**：
   - Evaluation Agent 输出信号 → 写入 `state_update` → 保存到上下文
   - 下次执行时读取 → 影响计划选择 → 改变执行路径

3. **闭环验证**：
   - trace 中可看到 `evaluation_feedback_flow` 字段
   - `plan_selection_history` 中记录是否使用了 Evaluation 反馈

**失败类型映射**（规则驱动）：
- `data_issue` → DEGRADED 计划（跳过数据节点）
- `execution_issue` → MINIMAL 计划（最小执行路径）
- `cost_issue` → DEGRADED 计划（降级以节省成本）

---

## 3. 成本感知调度与路径剪枝

### ✅ 已兑现

**实现位置**：
- `runtime/agents/cost_agent.py` - 成本监控
- `runtime/governance/governance_engine.py` - 预算检查
- `runtime/execution_plan/plan_selector.py` - 预算触发路径选择
- `runtime/execution_graph/execution_engine.py` - 动态路径切换

**关键特性**：
1. **成本作为一等信号**：
   - token / latency / retries 记录
   - 阶段性预算（per-stage budget）
   - 任务级预算（per-task budget）

2. **预算触发的真实路径剪枝**：
   - 超预算 → Governance 决策为 DEGRADED 或 MINIMAL
   - ExecutionPlan 实际切换到降级路径（不是只写 trace）
   - 记录到 `plan_selection_history` 中，包含 `trigger: "budget_or_governance_change"`

3. **动态切换**：
   - 执行过程中检测到预算不足 → 重新选择计划
   - 重新获取可执行节点 → 继续执行新计划

---

## 4. 工具调用与沙盒运行

### ✅ 已兑现

**实现位置**：
- `runtime/tools/tool_dispatcher.py` - 集中式工具调度入口
- `runtime/agents/execution_agent.py` - 通过 ToolDispatcher 调用工具

**关键特性**：
1. **集中式工具调度**：
   - 所有工具调用通过 ToolDispatcher.execute()
   - 统一的参数校验、权限检查、沙盒执行

2. **参数校验**：
   - JSON Schema 级别的校验
   - 必填字段检查
   - 类型检查

3. **权限边界**：
   - 文件路径白名单（artifacts/、runtime/tools/sandbox/）
   - 命令白名单（mkdir、cp、mv、ls、cat、echo）
   - 权限级别（READ_ONLY、WRITE_LOCAL、EXECUTE_SAFE、NETWORK_ACCESS）

4. **隔离执行**：
   - 每个 task 有独立的沙盒目录
   - 失败不会污染全局状态
   - 失败可诊断、可复现（exit_code、error_summary）

5. **可审计**：
   - trace 记录：tool_name、validated、exit_code、error_summary、degrade_triggered、rollback_triggered

---

## 5. 系统级治理与裁决

### ✅ 已兑现

**实现位置**：
- `runtime/governance/governance_engine.py` - 治理决策引擎
- `runtime/governance/conflict_detector.py` - 冲突检测
- `runtime/governance/agent_report.py` - Agent 报告结构

**关键特性**：
1. **规则驱动的治理决策**（非 LLM）：
   - 硬冲突 → PAUSED
   - 预算超限 → DEGRADED
   - 高风险 + 低置信度 → PAUSED
   - 多个 LLM fallback → DEGRADED
   - 软冲突 → MINIMAL
   - 其他 → NORMAL

2. **冲突检测**：
   - HARD / SOFT 冲突分类
   - 冲突严重性与决策映射可审计

3. **系统级裁决**：
   - GovernanceDecision 驱动 ExecutionPlan Selection
   - 所有决策记录到 trace 中

**可回答的问题**：
- Agents disagree then what? → 查看 `governance_decisions` 中的 `conflicts`
- 为什么暂停/降级/最小路径？ → 查看 `governance_decisions` 中的 `reasoning`
- 触发条件是什么？ → 查看 `governance_decisions` 中的 `metrics`

---

## 6. Trace / Artifacts 的审计增强

### ✅ 已兑现

**实现位置**：
- `runtime/execution_graph/execution_engine.py` - `_generate_artifacts()` 方法

**关键特性**：
1. **system_trace.json 包含三类关键事实**：
   - **AgentReports**：每个 Agent 的结构化输出（signals + decision + status）
   - **GovernanceDecisions**：每个检查点的系统决策（mode + reasoning + conflicts + metrics）
   - **ExecutionPlan**：
     - plan_id / plan_version
     - chosen_path（NORMAL/DEGRADED/MINIMAL）
     - executed_nodes（实际执行序列）
     - conditions_evidence（条件命中证据：来自 signals）
     - plan_selection_history（计划选择历史）

2. **工具调用记录**：
   - tool_executions：所有工具调用的完整记录
   - 每个 Agent 执行中的 tool_executions

3. **Evaluation 回流记录**：
   - evaluation_feedback_flow：记录回流信号和使用情况

4. **安全要求**：
   - 不记录完整 prompt（只记录 prompt_hash / prompt_version）
   - 不记录 raw LLM response（只记录 output_summary）
   - 允许记录 failure_code

---

## 7. 稳定性与复跑验证

### ✅ 已兑现

**系统设计保证**：
1. **连续执行支持**：
   - 状态机支持多次执行（IDLE → SPEC_READY → RUNNING → COMPLETED / FAILED）
   - 上下文可继承（Evaluation 反馈可跨任务使用）

2. **LLM 失败处理**：
   - LLM fallback 机制（不依赖 LLM 成功）
   - 治理层完全规则驱动（不依赖 LLM）

3. **失败处理**：
   - 任一 Agent / LLM / 治理层失败不影响系统进入 COMPLETED（除非治理明确 PAUSED/FAILED）
   - 系统行为稳定、可诊断、可复现

---

## 8. 底座红线保持

### ✅ 已兑现

**未改变的工程底座**：
1. ✅ 状态机语义与迁移：`IDLE → SPEC_READY → RUNNING → COMPLETED / FAILED`
2. ✅ `StateManager`：系统唯一状态写入者
3. ✅ `ExecutionEngine`：负责按计划执行节点，不拥有系统级裁决权
4. ✅ Agent 职责集合固定不变：`Product / Orchestrator / Data / Execution / Evaluation / Cost`
5. ✅ Agent 接口形态保持不变（`execute(context, task_id)`）
6. ✅ 对外审计产物不变：`system_trace.json`、`delivery_manifest.json`、`README.md`
7. ✅ `artifacts/` 目录结构与 schema 未破坏
8. ✅ 前端 Wizard 未改动

**新增内容**（不破坏兼容性）：
- 治理层（GovernanceEngine、ConflictDetector、AgentReport）
- 计划层（ExecutionPlan、PlanSelector、PlanRegistry）
- 决策解释层（plan_selection_history、conditions_evidence）
- 运行时元数据（tool_executions、evaluation_feedback_flow）

---

## 完成判定

### ✅ 全部满足

- ✅ 原项目描述每一条能力都有工程对应物
- ✅ ExecutionPlan 已显式化为可审计对象
- ✅ 计划选择是 **规则驱动、非学习型、可静态审计、非模型生成**
- ✅ Evaluation 信号真实回流并改变调度与执行路径
- ✅ 成本预算触发真实路径剪枝（不是日志）
- ✅ 工具调用具备参数校验 + 隔离执行 + 可审计
- ✅ 治理与裁决完全来自规则，不依赖 LLM 成功与否
- ✅ trace 能完整复盘：为什么这么跑、为什么降级、为什么暂停、为什么未失败
- ✅ 底座红线完全未被破坏（状态机/职责/接口/产物结构）

---

## 系统定位

> **"这不是 Agent Demo，而是一个稳定的工程 OS：  
通过显式 ExecutionPlan（条件 DAG）、系统级治理裁决、成本与风险风控、  
以及评测→调度闭环，把多智能体从不可控协作升级为可交付、可审计、可复现的工程交付系统。"**

✅ **完全成立**

---

## 审计证据

所有能力均可在以下文件中找到工程实现：

1. **ExecutionPlan 系统**：
   - `runtime/execution_plan/plan_definition.py`
   - `runtime/execution_plan/plan_registry.py`
   - `runtime/execution_plan/plan_selector.py`

2. **Evaluation 回流**：
   - `runtime/agents/evaluation_agent.py` (lines 33-57, 77-81)
   - `runtime/execution_graph/execution_engine.py` (lines 72-76, 178-200)

3. **成本感知路径剪枝**：
   - `runtime/governance/governance_engine.py` (lines 84-93)
   - `runtime/execution_plan/plan_selector.py` (lines 55-58)
   - `runtime/execution_graph/execution_engine.py` (lines 147-176)

4. **工具调用与沙盒**：
   - `runtime/tools/tool_dispatcher.py`
   - `runtime/agents/execution_agent.py` (lines 27-38)

5. **系统级治理**：
   - `runtime/governance/governance_engine.py`
   - `runtime/governance/conflict_detector.py`

6. **Trace 增强**：
   - `runtime/execution_graph/execution_engine.py` (lines 414-442)

---

**状态**：✅ **100% 工程化兑现完成**


