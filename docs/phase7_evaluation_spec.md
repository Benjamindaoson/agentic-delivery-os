# Phase 7 Evaluation Specification

> 本文档定义 Phase 7 评测系统的运行方法、资产结构、冻结纪律

## 1. 系统定位

Phase 7 的唯一目标是：

> **构建一套任何第三方都无法否认的、可复现、可对照、可审计的工程证据体系，**
> **证明该系统在什么情况下成立，在什么情况下保守，在什么情况下正确失败。**

---

## 2. 确定性与可复现纪律

### 2.1 Determinism 冻结（必须写死）

Phase 7 评测运行必须同时满足：

- ✅ 固定 `seed`（如系统存在随机性，必须对齐为同一个 seed）
- ✅ 固定 `model/provider`（如 baseline 使用 LLM，也必须固定版本标识）
- ✅ 固定 `tool/runtime` 版本（通过版本号或 git commit 记录）
- ✅ 固定 `config snapshot`（运行时导出完整配置快照）
- ✅ 固定 `input snapshot`（输入写入 artifacts 并计算 hash）
- ✅ 固定 `harness_version`（harness 代码版本必须记录）

### 2.2 Run 不可篡改资产（必须产出）

每一次评测运行必须产出一个不可变 run 目录（只可追加，不可覆盖）：

`artifacts/phase7/runs/{run_id}/`

其中 `run_id` 必须由以下字段确定性生成：
- timestamp（仅用于区分，不用于排序判断）
- git_commit
- harness_version
- suite_version
- system_matrix_hash（系统集合定义的 hash）
- task_suite_hash（任务集合定义的 hash）

---

## 3. 运行方法

### 3.1 一键运行

```bash
python scripts/run_phase7_evaluation.py
```

### 3.2 运行前准备

1. 计算 task_suite hash:
```bash
python runtime/eval/task_suite_hasher.py
```

2. 计算 system_matrix hash:
```bash
python runtime/eval/system_matrix_hasher.py
```

3. 计算 metrics_registry hash:
```bash
python runtime/eval/metrics_registry_hasher.py
```

---

## 4. 资产结构

### 4.1 Run 目录结构

```
artifacts/phase7/runs/{run_id}/
├── run_metadata.json          # 运行元数据（确定性）
└── case_results.json          # 所有 case 结果
```

### 4.2 Case 目录结构

```
artifacts/phase7/cases/{task_id}/{system_id}/
├── input_snapshot.json         # 输入快照（与 fixed_input_spec 一致）
├── input_hash.txt              # 输入 hash
├── run_metadata.json           # 运行元数据
├── trace_export.json           # Trace 导出
├── replay_view.json            # Replay view（event-order replay）
├── cost_outcome.json          # 成本结果（含预测/实际/偏差）
├── failure_explain.json       # 失败解释（如适用）
├── metrics.json                # 指标
├── export_audit_pack.zip       # 导出审计包
└── case_hash.txt               # Case 目录整体 hash
```

### 4.3 Summary 目录结构

```
artifacts/phase7/summary/
├── leaderboard_{run_id}.json  # 汇总结果（JSON）
├── leaderboard_{run_id}.csv   # 汇总结果（CSV）
└── summary_hash.txt            # 汇总 hash
```

---

## 5. Replay 时间模型（必须明确）

Replay 必须使用：
- **event-order replay（事件顺序回放）**

明确声明：
- 非真实 wall-clock
- 非执行耗时比例
- 不用于性能推断
- 仅用于因果与决策顺序验证

在 `replay_view.json` 中必须包含：
```json
{
  "time_model": "event-order_replay",
  "time_model_declaration": "This is logical execution order replay, not wall-clock time. Not execution duration ratio. Not physical time axis. Only for causal and decision order verification."
}
```

---

## 6. Counterfactual Cost 对照（严格约束）

所有"如果不剪枝会怎样"的分析必须满足：

- 明确标注为：`deterministic_counterfactual_estimation`
- 基于 `plan_definition` 的全路径静态展开
- 基于节点级确定性成本规则估算
- 不依赖真实执行
- 不假设该路径会成功
- 不等价于 replay

在 `cost_outcome.json` 中必须包含：
```json
{
  "counterfactual_estimation": {
    "type": "deterministic_counterfactual_estimation",
    "declaration": "Based on plan_definition full path static expansion. Based on node-level deterministic cost rules. Not dependent on real execution. Not assuming path will succeed. Not equivalent to replay."
  }
}
```

---

## 7. 冻结规则

- ✅ 结果不可"重跑以变好"
- ✅ 只能新增新任务或新系统
- ✅ 只能新增新 run_id
- ✅ 旧 run 目录不可修改（hash 校验必须能发现任何变动）

---

## 8. 禁止事项

- ❌ 不允许解释性文字替代证据
- ❌ 不允许 narrative 引导结论
- ❌ 不允许挑选"有利任务"
- ❌ 不允许隐藏失败样本
- ❌ 不允许"重跑直到变好"
- ❌ 不允许手工改写任何结果文件（除非以新的 run_id 追加生成）

---

**状态**: ✅ **Phase 7 Evaluation Specification 已定义**


