# Phase 6 前端展示升级规格说明

> 本文档定义 Phase 6 前端展示层的工程级约束与实现规格

## 1. 总原则（可验收）

- **前端 = 可视化映射，不是创作**
- 所有展示基于 trace / decision / metric 证据
- 所有"为什么"均可点回 event_id / sequence_id / metric_ref
- 视觉一致性通过 Design Tokens 强制

---

## 2. Replay View 的时间语义（工程级写死）

### 2.1 时间模型声明（强制）

**Replay View 使用的时间模型必须明确、唯一、不可切换：**

> **Event-Order Replay（事件顺序回放）**

#### 明确声明：
- Replay Timeline **不是 wall-clock 时间**
- Replay Timeline **不是执行耗时比例**
- Replay Timeline **不是物理时间轴**

#### Replay Timeline 表示的是：
- `event_sequence_index` 的 **逻辑顺序**
- 即：系统在"第几个关键事件之后，状态发生了什么变化"

### 2.2 工程定义（必须落实）

- Timeline 的横轴单位为：`event_index`
- 每一个可拖动位置 = 某一个或某一组 `trace_event.sequence_id`
- Checkpoint（after_product / after_data / after_execution / after_evaluation）：
  - 是 **事件集合边界**
  - 不是时间点
- 不允许在 UI 中展示任何 wall-clock 时间比例轴

### 2.3 对外口径（必须统一）

对外解释 Replay 时，只允许以下一句话：

> "这是 **逻辑执行顺序回放**，用于复盘系统决策路径，  
> 而不是还原真实执行耗时。"

任何偏离此口径的说明视为违规。

### 2.4 实现位置

- `frontend/src/components/ReplayTimeline.tsx`
- `frontend/src/pages/ExecutionReplay.tsx`
- API: `GET /api/task/{id}/trace/events`

---

## 3. Cost–Outcome 视图的反事实语义（工程级写死）

### 3.1 Counterfactual 明确定义（强制）

Cost–Outcome 页面中的：

> "如果不剪枝会怎样"

**必须被明确标注为：**

> **Deterministic Counterfactual Cost Estimation**

### 3.2 工程级语义声明（必须写在 spec）

该对照满足：
- 基于 `plan_definition` 的 **全路径静态展开**
- 基于节点级确定性成本规则估算
- **不依赖真实执行**
- **不假设该路径一定会成功执行**

明确声明：

> 该结果是 **反事实成本估算（counterfactual estimate）**，  
> 用于衡量剪枝/降级的工程价值，  
> **不代表系统真实可能执行的路径**。

### 3.3 UI 约束（必须）

- 页面必须显式标注：
  - "Estimated (Counterfactual)"
  - "Not a Replay"
- 禁止将该视图与 Replay View 混用时间轴或样式
- 禁止使用"如果当时没剪枝就会……"等叙述性语言

### 3.4 实现位置

- `frontend/src/pages/CostOutcome.tsx`

---

## 4. Failure Explain View

### 4.1 页面目标

用证据解释失败原因：
- 失败类型
- 归因线索
- 相关治理决策
- 证据事件

### 4.2 实现位置

- `frontend/src/pages/FailureExplain.tsx`

---

## 5. 视觉一致性的工程级约束

### 5.1 Design Token 强制要求

前端必须定义 **集中式 Design Tokens**，至少包含：

- **Spacing scale**: xs (4px), sm (8px), md (12px), lg (16px), xl (24px), xxl (32px), xxxl (48px)
- **Color tokens**: background, surface, border, accent, success, warning, danger, info, textPrimary, textSecondary
- **Typography tokens**: fontFamily (sans, mono), fontSize (xs-xxxl), fontWeight (normal-bold), lineHeight
- **Border radius**: sm (4px), md (8px), lg (12px), xl (16px), full
- **Shadows**: sm, md, lg, xl
- **Transitions**: fast (150ms), normal (250ms), slow (350ms)

### 5.2 工程约束（硬规则）

- 所有页面与组件 **不得自行定义颜色、间距、字体**
- 所有样式必须引用统一 token
- 禁止 inline magic numbers（如 padding: 13px）
- 新页面必须复用既有 layout / card / drawer 组件

违反以上任一条视为 Phase 6 未完成。

### 5.3 实现位置

- `frontend/src/design/tokens.ts`

---

## 6. 核心页面结构

### 6.1 Execution Replay View

**页面结构（冻结）**:

#### A. 顶栏 KPI
- Task Status
- Execution Mode
- Accumulated Cost
- Key Event Counts

#### B. Replay Timeline（逻辑序列）
- 横轴：event_sequence_index
- 节点：checkpoint（事件边界）
- 拖动 = 在 **事件序列中跳转**

#### C. Evidence Drawer（证据抽屉）
必须展示：
- event_id
- sequence_id
- 对应 trace 位置
- governance_decision / evaluation / tool_result

**实现位置**: `frontend/src/pages/ExecutionReplay.tsx`

---

## 7. API 与数据约束

- 前端只读
- 不写 trace
- 不改决策
- 只展示结构化证据

**数据来源**:
- `GET /api/task/{id}/trace/summary` - 摘要
- `GET /api/task/{id}/trace/events` - 事件流
- `GET /api/task/{id}/trace` - 完整 trace（按需）

---

## 8. 不可验收条款

以下行为直接判定 Phase 6 失败：
- Replay 时间语义不清
- Counterfactual 与 Replay 混淆
- 视觉规范靠"约定"而非 token
- 任意自由文本解释系统行为

---

## 9. 验收标准

Phase 6 仅当 **全部成立** 才算完成：

- ✅ Replay View 明确为 **event-order replay**
- ✅ Cost–Outcome 明确为 **deterministic counterfactual estimation**
- ✅ 所有页面使用统一 design tokens
- ✅ 所有"为什么"均可点回 event_id / sequence_id / metric_ref
- ✅ Docs 齐全：
  - phase6_ui_spec.md（本文档）
  - phase6_ui_evidence.md
  - phase6_demo_script.md
  - phase6_acceptance_checklist.md

---

## 10. 唯一允许的对外表述

> "这是一个基于 **逻辑事件顺序回放** 的 Multi-Agent 工程交付系统前端。  
> 它通过可审计证据复盘系统决策路径，并用确定性的反事实估算展示成本剪枝价值。"

---

**状态**: ✅ **Phase 6 UI 规格已定义**


