# Phase 6 前端展示升级实现证据

> 本文档提供 Phase 6 前端展示层的实现证据与验证方法

## 1. 实现文件清单

### 1.1 Design Tokens

- ✅ `frontend/src/design/tokens.ts` - 集中式样式规范

**验证方法**:
```typescript
// 检查所有页面是否导入 tokens
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

// 检查是否使用 magic numbers
// 禁止：padding: 13px
// 允许：padding: spacing.md
```

### 1.2 Replay Timeline 组件

- ✅ `frontend/src/components/ReplayTimeline.tsx` - 事件顺序回放组件
- ✅ `frontend/src/pages/ExecutionReplay.tsx` - 执行回放视图页面

**验证方法**:
1. 检查时间语义声明是否显示
2. 检查横轴是否标注为 `event_sequence_index`
3. 检查是否禁止 wall-clock 时间显示

### 1.3 Cost–Outcome 视图

- ✅ `frontend/src/pages/CostOutcome.tsx` - 成本-结果分析页面

**验证方法**:
1. 检查是否显式标注 "Estimated (Counterfactual)"
2. 检查是否标注 "Not a Replay"
3. 检查是否禁止叙述性语言

### 1.4 Failure Explain 视图

- ✅ `frontend/src/pages/FailureExplain.tsx` - 失败解释页面

---

## 2. 时间语义验证

### 2.1 Replay Timeline 语义验证

**检查点**:
1. ✅ 页面是否显示"逻辑执行顺序回放"说明
2. ✅ 横轴是否标注为 `event_sequence_index`
3. ✅ 是否禁止 wall-clock 时间显示
4. ✅ Checkpoint 是否标注为"事件边界"

**代码证据**:
```typescript
// frontend/src/components/ReplayTimeline.tsx
<div style={{...}}>
  <strong>时间语义说明：</strong>
  这是 <strong>逻辑执行顺序回放</strong>，用于复盘系统决策路径，而不是还原真实执行耗时。
  横轴单位为 <code>event_sequence_index</code>（事件序列索引）。
</div>
```

---

## 3. 反事实语义验证

### 3.1 Cost–Outcome 语义验证

**检查点**:
1. ✅ 页面是否显式标注反事实说明
2. ✅ 是否标注 "Estimated (Counterfactual)"
3. ✅ 是否标注 "Not a Replay"
4. ✅ 是否禁止叙述性语言

**代码证据**:
```typescript
// frontend/src/pages/CostOutcome.tsx
<div style={{ backgroundColor: colors.warning, ... }}>
  <h3>⚠️ 反事实估算说明</h3>
  <p>
    该视图展示的是 <strong>确定性反事实成本估算（Deterministic Counterfactual Cost Estimation）</strong>。
    基于 <code>plan_definition</code> 的全路径静态展开和节点级确定性成本规则估算。
    <strong>不依赖真实执行，不假设该路径一定会成功执行。</strong>
  </p>
</div>
```

---

## 4. Design Tokens 验证

### 4.1 Token 使用验证

**检查方法**:
```bash
# 检查是否有 magic numbers
grep -r "padding: [0-9]\+px" frontend/src/pages
grep -r "color: '#[0-9a-fA-F]\{6\}'" frontend/src/pages
grep -r "fontSize: '[0-9]\+px'" frontend/src/pages

# 应该返回空或只有 tokens.ts 中的定义
```

### 4.2 Token 导入验证

**检查方法**:
```bash
# 检查所有页面是否导入 tokens
grep -r "from '../design/tokens'" frontend/src/pages
grep -r "from '../../design/tokens'" frontend/src/components
```

---

## 5. 证据绑定验证

### 5.1 Evidence Drawer 验证

每个事件必须可追溯：
- event_id
- sequence_id
- trace_location

**验证方法**:
1. 点击 Timeline 上的事件节点
2. 检查 Evidence Drawer 是否显示完整证据
3. 检查 trace_location 是否可定位

---

## 6. 视觉一致性验证

### 6.1 样式一致性

**检查方法**:
1. 打开所有页面
2. 检查间距、颜色、字体是否一致
3. 检查是否使用统一 tokens

### 6.2 组件复用

**检查方法**:
1. 检查是否有重复的样式定义
2. 检查是否复用 layout / card / drawer 组件

---

## 7. 完成判定

Phase 6 完成当且仅当：

- ✅ Replay View 明确为 event-order replay
- ✅ Cost–Outcome 明确为 deterministic counterfactual estimation
- ✅ 所有页面使用统一 design tokens
- ✅ 所有"为什么"均可点回 event_id / sequence_id / metric_ref
- ✅ 无 magic numbers
- ✅ 无自由文本解释系统行为

---

**状态**: ✅ **Phase 6 UI 实现证据已记录**


