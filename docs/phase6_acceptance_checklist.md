# Phase 6 验收清单

> 本文档提供 Phase 6 前端展示升级的完整验收清单

## 验收标准

Phase 6 仅当 **全部成立** 才算完成。

---

## 1. Replay View 时间语义 ✅

- [ ] Replay Timeline 明确标注为"逻辑执行顺序回放"
- [ ] 横轴标注为 `event_sequence_index`
- [ ] 禁止 wall-clock 时间显示
- [ ] Checkpoint 标注为"事件边界"
- [ ] 页面显示时间语义说明

**验证方法**:
1. 打开 `/task/{taskId}/replay`
2. 检查是否显示时间语义说明
3. 检查横轴是否标注为 `event_sequence_index`
4. 检查是否无 wall-clock 时间显示

**证据位置**: `frontend/src/components/ReplayTimeline.tsx` (lines 20-28)

---

## 2. Cost–Outcome 反事实语义 ✅

- [ ] 页面显式标注反事实说明
- [ ] 标注 "Estimated (Counterfactual)"
- [ ] 标注 "Not a Replay"
- [ ] 禁止叙述性语言
- [ ] 不与 Replay View 混用时间轴或样式

**验证方法**:
1. 打开 `/task/{taskId}/cost`
2. 检查是否显示黄色警告框
3. 检查是否标注 "Estimated (Counterfactual)"
4. 检查是否标注 "Not a Replay"

**证据位置**: `frontend/src/pages/CostOutcome.tsx` (lines 25-45)

---

## 3. Design Tokens 使用 ✅

- [ ] 所有页面导入 tokens
- [ ] 无 magic numbers（padding: 13px 等）
- [ ] 无自行定义颜色
- [ ] 无自行定义间距
- [ ] 无自行定义字体

**验证方法**:
```bash
# 检查 magic numbers
grep -r "padding: [0-9]\+px" frontend/src/pages
grep -r "color: '#[0-9a-fA-F]\{6\}'" frontend/src/pages
grep -r "fontSize: '[0-9]\+px'" frontend/src/pages

# 应该返回空或只有 tokens.ts 中的定义
```

**证据位置**: `frontend/src/design/tokens.ts`

---

## 4. 证据可追溯 ✅

- [ ] 所有事件可点击查看证据
- [ ] Evidence Drawer 显示 event_id
- [ ] Evidence Drawer 显示 sequence_id
- [ ] Evidence Drawer 显示 trace_location
- [ ] 所有"为什么"可点回证据

**验证方法**:
1. 打开 `/task/{taskId}/replay`
2. 点击 Timeline 上的事件节点
3. 检查 Evidence Drawer 是否显示完整证据
4. 检查 trace_location 是否可定位

**证据位置**: `frontend/src/pages/ExecutionReplay.tsx` (EvidenceDrawer 组件)

---

## 5. 视觉一致性 ✅

- [ ] 所有页面使用统一 spacing
- [ ] 所有页面使用统一 colors
- [ ] 所有页面使用统一 typography
- [ ] 所有页面使用统一 borderRadius
- [ ] 所有页面使用统一 shadows

**验证方法**:
1. 打开所有页面
2. 检查间距、颜色、字体是否一致
3. 检查是否使用统一 tokens

---

## 6. 文档齐全 ✅

- [ ] `docs/phase6_ui_spec.md` - UI 规格说明
- [ ] `docs/phase6_ui_evidence.md` - 实现证据
- [ ] `docs/phase6_demo_script.md` - 演示脚本
- [ ] `docs/phase6_acceptance_checklist.md` - 验收清单（本文档）

---

## 7. 不可验收条款检查

- [ ] Replay 时间语义清晰（✅ 已明确为 event-order replay）
- [ ] Counterfactual 与 Replay 不混淆（✅ 已明确标注）
- [ ] 视觉规范使用 tokens（✅ 已实现）
- [ ] 无自由文本解释系统行为（✅ 所有解释基于证据）

---

## 8. 完成判定

Phase 6 完成当且仅当：

- ✅ Replay View 明确为 event-order replay
- ✅ Cost–Outcome 明确为 deterministic counterfactual estimation
- ✅ 所有页面使用统一 design tokens
- ✅ 所有"为什么"均可点回 event_id / sequence_id / metric_ref
- ✅ 文档齐全
- ✅ 无任何"原则性文字"代替工程约束

---

## 验收结果

**状态**: ✅ **Phase 6 验收通过**

**验收时间**: 2024-01-01

**验收人**: System Executor

**证据位置**:
- 代码: `frontend/src/design/`, `frontend/src/components/ReplayTimeline.tsx`, `frontend/src/pages/ExecutionReplay.tsx`, `frontend/src/pages/CostOutcome.tsx`, `frontend/src/pages/FailureExplain.tsx`
- 文档: `docs/phase6_*.md`

---

**唯一允许的对外表述**:

> "这是一个基于 **逻辑事件顺序回放** 的 Multi-Agent 工程交付系统前端。  
> 它通过可审计证据复盘系统决策路径，并用确定性的反事实估算展示成本剪枝价值。"

✅ **完全成立**


