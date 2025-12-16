# Phase 8 Change Log

> 记录为实现 Production-Grade RAG Pipeline 所做的所有工程变更，确保可审计与可回滚。

## 2026-Phase8-001 — 运行入口与一键命令统一

- **修改文件**
  - `Makefile`
  - `scripts/run_backend.py`
- **变更内容**
  - 新增统一一键命令：`make setup / test / build / run / eval / deploy`，对应 Python/Node 依赖安装、pytest、前端构建、后端启动、评测脚本、docker compose 部署。
  - 新增 `scripts/run_backend.py`，在运行时自动将仓库根目录加入 `PYTHONPATH`，通过 `uvicorn.run("backend.main:app", ...)` 启动 FastAPI 后端，作为本地与 CI 的统一入口。
- **对应要求**
  - Phase 8 Prompt：第 1.1 节（Hard Completion Gate）中的 `make setup/test/build/run/eval/deploy`
  - Phase 8 Prompt：第 7 节（运行入口与一键命令）
- **是否属于降级**
  - NO（仅统一入口与命令，不削弱既有能力）
- **风险评估**
  - low：依赖现有 `backend.main:app`，不改变业务逻辑，仅封装启动方式。
- **回滚方式**
  - 使用 `git revert` 回滚本次提交，删除 `Makefile` 中新增目标与 `scripts/run_backend.py`，同时可恢复到原有手工命令启动方式。

---

## 2026-Phase8-002 — Offline DQ Engine（P0）

- **修改文件**
  - `backend/offline/__init__.py`
  - `backend/offline/dq_engine.py`
  - `configs/dq_config.yaml`
  - `schemas/dq_report.schema.json`
  - `tests/test_dq_engine.py`
- **变更内容**
  - 新增 DQ Engine 模块 `backend/offline/dq_engine.py`：
    - 计算文档级数据质量指标：`ocr_coverage`、`table_recovery_rate`、`empty_page_ratio`、`duplicate_page_ratio`、`language`。
    - 基于可配置阈值（`configs/dq_config.yaml`）输出决策等级：`PASS` / `WARN` / `FAIL`，并附带 `reasons`。
    - 生成结构化 `dq_report`，并通过 `persist_dq_report` 落盘到 `artifacts/offline/{doc_id}/{run_id}/dq_report.json`。
  - 新增 DQ 配置文件 `configs/dq_config.yaml`，将各项阈值从代码中抽离为配置。
  - 新增 JSON Schema `schemas/dq_report.schema.json`，约束 `dq_report.json` 的结构，确保可审计与向后兼容。
  - 新增单元测试 `tests/test_dq_engine.py`，覆盖：
    - 至少一个 PASS 场景（高质量解析文档）。
    - 至少一个 FAIL 场景（大量空页/无 OCR/表格恢复失败）。
- **对应要求**
  - Phase 8 宪法：P0 — DQ Engine（Offline Pipeline 的裁判），需输出 `dq_report.json` 并以阈值驱动 PASS/WARN/FAIL。
- **是否属于降级**
  - NO：新增质量门禁与度量，未削弱既有能力；后续可替换内部启发式为更精细统计而不破坏对外契约。
- **风险评估**
  - medium：门禁逻辑引入新的 FAIL/WARN 决策，后续接入 Offline Pipeline 时需确保对已有数据进行回溯验证。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 DQ Engine 模块、配置与 schema，并移除相关测试（`tests/test_dq_engine.py`）。

---

## 2026-Phase8-003 — Parser Strategy Selector（P0）

- **修改文件**
  - `backend/offline/parser_selector.py`
  - `backend/offline/__init__.py`
  - `tests/test_parser_selector.py`
- **变更内容**
  - 新增 Parser Strategy Selector 模块 `backend/offline/parser_selector.py`：
    - 基于 `doc_meta`（`mime`、`has_ocr`、`has_tables`、`page_count`、`text_density`）输出结构化决策：
      - `doc_type`: `digital_pdf | scanned_pdf | table_heavy`
      - `strategy`: 如 `["text"]`、`["ocr","layout","table"]`、`["text","table"]`
      - `confidence`: 0–1 的确定性置信度
    - 规则驱动、静态可审计，不在 worker 内写散乱 if/else。
  - 新增测试 `tests/test_parser_selector.py` 覆盖至少两种文档类型：
    - `scanned_pdf`：低 text_density、无 OCR。
    - `table_heavy`：存在表格、页数>0。
- **对应要求**
  - Phase 8 宪法：P0 — Parser Strategy Selector，必须是显式策略决策模块，输出可审计 JSON 结构。
- **是否属于降级**
  - NO：仅新增解析策略决策逻辑，后续接入实际解析流水线时会作为决策前置；未削弱既有能力。
- **风险评估**
  - low：目前仅作为独立决策模块和测试存在，尚未影响生产解析路径。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `parser_selector` 模块与对应测试。

---

## 2026-Phase8-004 — Offline HITL 自动触发与局部重建骨架（P1）

- **修改文件**
  - `runtime/hitl/__init__.py`
  - `runtime/hitl/offline_hitl.py`
  - `runtime/hitl/apply_patch.py`
  - `tests/test_offline_hitl_partial_rebuild.py`
- **变更内容**
  - 新增 Offline HITL 工具包 `runtime/hitl`：
    - `offline_hitl.create_hitl_task_for_warn(job_id, parsed_doc)`：
      - 基于 DQMetrics 生成标准 HITL Task，路径固定为 `artifacts/hitl_queue/{job_id}.json`。
      - 结构符合宪法要求：`job_id`、`stage`、`trigger=DQ_WARN`、`issues[]`、`allowed_patch_types[]`、`created_at`。
      - `issues` 严格来源于 DQ 信号（`ocr_coverage` / `table_recovery_rate`），不做随机生成。
    - `apply_patch.apply_patch(patch)`：
      - 校验 patch 合法性（job_id 存在、patch_type 在 allowed_patch_types 中）。
      - 只对 `ParsedDoc` / `tables` / `chunks` 做最小局部更新，不触碰原始文档。
      - 重跑 DQ Gate，落盘新的 `dq_report.json`，并返回 `status`（`ready_to_continue|still_in_hitl|failed`）与 `dq_level`。
  - 新增测试 `tests/test_offline_hitl_partial_rebuild.py`：
    - 构造 DQ 非 PASS 的 ParsedDoc，确认 WARN/FAIL 场景下会生成或存在 HITL Task。
    - 应用 `ocr_cell` patch 后，重新运行 DQ，并在 `dq_level == PASS` 时断言 `status == "ready_to_continue"`，验证“修复后可继续 Offline Pipeline”的最小闭环骨架。
- **对应要求**
  - Phase 8 宪法 P1：Offline HITL 自动触发 + 局部重建：
    - DQ = WARN → 生成 HITL Task（非装饰队列）。
    - Patch 合同：最小、局部、可审计，不可修改原始文档。
    - Patch 后重跑 DQ Gate，并按 PASS/WARN/FAIL 决定是否恢复 Pipeline。
- **是否属于降级**
  - NO：在现有 Offline Pipeline 能力基础上增加 HITL 与局部重建骨架，不移除或弱化任何既有功能；后续可在该骨架上接入更精细的 page/table/chunk 级逻辑。
- **风险评估**
  - medium：当前局部重建仅更新 ParsedDoc 与 DQ 报告，尚未接入真实 chunk/embed/index delta 流程；后续接入时需确保不会触发全量重建。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `runtime/hitl/*` 与 `tests/test_offline_hitl_partial_rebuild.py`。

---

## 2026-Phase8-005 — Risk-Tier 进入 Online Pipeline 骨架（P2）

- **修改文件**
  - `backend/online/__init__.py`
  - `backend/online/risk_tier.py`
  - `backend/online/pipeline.py`
  - `tests/test_risk_tier_online.py`
- **变更内容**
  - 新增 Risk-Tier 引擎 `backend/online/risk_tier.py`：
    - 定义 `RiskTierDecision(risk_tier, source, confidence)`，支持 R0–R4。
    - `determine_risk_tier(profile, query, explicit_tier)`：
      - 优先使用显式指定 Tier。
      - 其次根据 profile（finance/edu/general）推断基线风险。
      - 最后通过 Query 关键字推断风险（金融/高危/非法场景 → R3/R4）。
      - 返回 `{"risk_tier":"Rx","source":"explicit|profile|query|profile+query","confidence":...}`。
    - `build_online_plans(decision)`：
      - 根据 Tier 生成检索 / 重排 / 验证 / HITL 策略矩阵：
        - Retrieval：R0=dense, R1=hybrid_light, R2/R3=hybrid_full（R3 增加 metadata_filter），R4=blocked。
        - Rerank：R0=none, R1=rule, R2=rule+model, R3=rule+model+llm, R4=blocked。
        - Verification：R0=basic, R1=claim, R2=claim+span, R3=claim+span+numeric, R4=blocked。
        - HITL：R3 在证据不足时强制人工，R4 直接拒答并进入 HITL。
  - 新增 Online Pipeline 骨架 `backend/online/pipeline.py`：
    - `run_online_query(profile, query, language, index_version, mode, explicit_risk_tier)`：
      - 调用 Risk-Tier 引擎与 plan builder，生成：
        - `answer`（当前为 stub / 空字符串，用于测试）。
        - `verification`（包含 passed/reasons/risk_level 占位）。
        - `trace`：记录 `risk_tier`、`retrieval_plan`、`rerank_plan`、`verification_plan`、`hitl_policy`、`hitl_triggered` 等，用于审计。
      - 对 R4：强制 `answer=""`、`verification.passed=False`、`hitl_triggered=True`，模拟“拒答 + HITL”行为。
  - 新增测试 `tests/test_risk_tier_online.py`：
    - 覆盖：
      - R0 查询 → dense-only + 无重排 + basic verification，且 `hitl_triggered=False`。
      - R3 查询 → finance profile + 高风险关键词 → `retrieval.mode=hybrid_full`、`metadata_filter=True`、`rerank=rule+model+llm`、`verification=claim+span+numeric`。
      - R4 查询 → 包含非法/洗钱关键词 → plan 全部 blocked，`answer=""`、`verification.passed=False`、`hitl_triggered=True`。
- **对应要求**
  - Phase 8 宪法 P2：Risk-Tier 成为 Online Pipeline 一级控制变量，驱动 Retrieval / Rerank / Verification / HITL 行为。
- **是否属于降级**
  - NO：仅新增 Online Risk-Tier 决策与计划骨架，尚未改变现有在线行为路径；未来接入真实检索/生成时会沿用同一决策矩阵。
- **风险评估**
  - low：当前仅作为独立组件和测试存在，不影响现有执行路径；接入真实 Online API 前可迭代规则细节。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `backend/online/*` 与 `tests/test_risk_tier_online.py`。

---

## 2026-Phase8-006 — Eval = Release Gate & Promote / Rollback（P3）

- **修改文件**
  - `configs/release_gate.yaml`
  - `scripts/promote.py`
  - `scripts/rollback.py`
  - `tests/test_release_gate_and_promote.py`
- **变更内容**
  - 新增 Release Gate 配置文件 `configs/release_gate.yaml`：
    - 记录离线与在线评测的默认阈值（`offline.ocr_coverage_min`、`offline.table_recovery_f1_min`、`online.retrieval_recall_at_5_min`、`online.generation_faithfulness_min`、`online.refusal_correct_refusal_rate_min`）以及构建要求（`require_tests_green`、`require_build_green`）。
    - 所有 Gate 逻辑从代码中抽离到配置层，符合“Gate 不得写死在代码”的宪法要求。
  - 新增 Promote 指针脚本 `scripts/promote.py`：
    - 通过 `artifacts/release/active.json` 维护当前激活的 `{index_version, model_version, config_version}`。
    - 将每次 promote 行为（from/to/timestamp）以追加行写入 `artifacts/release/history.jsonl`，形成可审计的发布历史。
    - 命令行用法：`python -m scripts.promote <index_version> [model_version] [config_version]`。
  - 新增 Rollback 脚本 `scripts/rollback.py`：
    - 从 `history.jsonl` 中读取最近一次 promote 记录，回退到其 `from` 指针（上一个稳定版本）。
    - 更新 `active.json` 并追加一条 rollback 行到 `history.jsonl`，记录回退前后状态。
    - 命令行用法：`python -m scripts.rollback`。
  - 新增测试 `tests/test_release_gate_and_promote.py`：
    - `test_release_gate_blocks_promote`：在临时目录下创建最小 `release_gate.yaml`，构造 `passed=False` 的 eval 结果，验证 `_gate_allows_promote(...)` 返回 False，模拟“Eval 未通过 → 禁止 promote”的 Gate 行为。
    - `test_promote_and_rollback`：在临时目录下模拟两次 `promote`（index_v1→index_v2），随后执行 `rollback()`，验证 `active.json` 中的指针成功回退到 `index_v1/model_v1/config_v1`，证明“一键回退”能力。
- **对应要求**
  - Phase 8 宪法 P3：Eval = Release Gate，Gate 未通过禁止 promote；Promote/rollback 必须基于指针切换，并具备一键回退能力。
- **是否属于降级**
  - NO：Release Gate 只增加治理约束，不移除或弱化任何现有功能；未来接入真实 Eval Suite 时，将以本配置与脚本为基础落地完整 Gate 流程。
- **风险评估**
  - low：当前 Gate 判定函数 `_gate_allows_promote` 仅在测试内使用，后续接入 CI/CD 与 eval harness 时需补充与实际 metrics 的映射。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `configs/release_gate.yaml`、`scripts/promote.py`、`scripts/rollback.py` 与对应测试。

---

## 2026-Phase8-007 — DQ Regression Guard（P4-1）

- **修改文件**
  - `backend/offline/dq_regression_guard.py`
  - `tests/test_dq_regression_guard.py`
- **变更内容**
  - 新增 DQ Regression Guard 模块 `backend/offline/dq_regression_guard.py`：
    - 实现函数 `check_dq_regression(current_dq: dict, previous_dq: dict | None) -> dict`。
    - 硬编码比较四个指标：
      - `ocr_coverage`（current < previous → 回归）
      - `table_recovery_f1`（current < previous → 回归）
      - `empty_page_ratio`（current > previous → 回归）
      - `duplicate_page_ratio`（current > previous → 回归）
    - 当 `previous_dq is None` 时直接返回 `{"regression_detected": False, "failed_metrics": []}`。
    - 返回结构固定为：`{"regression_detected": bool, "failed_metrics": [...]}`。
  - 新增测试 `tests/test_dq_regression_guard.py`：
    - `test_dq_regression_no_previous`：`previous_dq=None` → 不应检测到回归（`regression_detected=False`，`failed_metrics=[]`）。
    - `test_dq_regression_detects_worse_metrics`：构造当前指标明显劣于历史指标的场景，断言 `regression_detected=True`，且四个指标都被标记为回归。
- **对应要求**
  - Phase 8 · P4-1：DQ Regression Guard，确保同一数据源/同一 profile 下 DQ 指标不会倒退。
- **是否属于降级**
  - NO：当前模块仅作独立 Guard，不接入主 Offline Pipeline，不修改任何现有执行路径。
- **风险评估**
  - low：逻辑简单且有直观单测覆盖，后续接入 promote/index gate 时需确保正确关联到相同 source_id/profile 的 stable 报告。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `backend/offline/dq_regression_guard.py` 与 `tests/test_dq_regression_guard.py`。

---

## 2026-Phase8-008 — Typed / Multi-Vector Index Strategy（P4-3）

- **修改文件**
  - `schemas/chunk.schema.json`
  - `backend/offline/index_builder.py`
  - `schemas/index_manifest.schema.json`
  - `tests/test_index_strategy_map.py`
- **变更内容**
  - 新增 Chunk Schema `schemas/chunk.schema.json`：
    - 定义 `chunk_type` 字段及枚举值：`["clause","numeric_table","faq","timeline"]`，为后续 Typed Index 策略提供类型基础。
  - 新增 Index Builder 模块 `backend/offline/index_builder.py`：
    - 硬编码不同 `chunk_type` 的索引策略映射：
      - `numeric_table` → `["value_store","vector"]`
      - `clause` → `["dense","sparse"]`
      - `faq` → `["dense"]`
      - `timeline` → `["sparse","metadata"]`
    - 提供函数 `build_index_with_strategies(chunks, chunk_strategy, embedding_model, bm25)`：
      - 基于传入 chunks 的 `chunk_type` 构建 `index_strategy_map`，并合并进现有 `build_index_manifest` 输出。
  - 新增 Index Manifest Schema `schemas/index_manifest.schema.json`：
    - 增加 `index_strategy_map` 字段定义，类型为 `object`，用于约束 Manifest 中的策略映射结构。
  - 新增测试 `tests/test_index_strategy_map.py`：
    - `test_index_strategy_map_per_chunk_type`：校验四种 `chunk_type` 映射到预期的策略列表。
    - `test_numeric_table_not_dense_only`：确保 `numeric_table` 的策略中不包含 `"dense"`，而是 `["value_store","vector"]`，防止错误配置为 dense-only。
- **对应要求**
  - Phase 8 · P4-3：Typed / Multi-Vector Index Strategy，不同内容禁止混用同一索引策略，必须通过 IndexManifest 中的 `index_strategy_map` 显式记录。
- **是否属于降级**
  - NO：仅新增 Typed 策略定义与测试，尚未强制接入现有 Offline Pipeline，不改变当前索引构建行为。
- **风险评估**
  - low：逻辑集中且受单测保护，后续接入 Pipeline 时需保证与实际 chunk 结构和索引后端保持一致。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除新增 Schema、Index Builder 模块与测试。

---

## 2026-Phase8-009 — HITL Learning Loop（P5-1）

- **修改文件**
  - `backend/learning/__init__.py`
  - `backend/learning/hitl_learning_engine.py`
  - `tests/test_hitl_learning_loop.py`
- **变更内容**
  - 新增 HITL 学习引擎 `backend/learning/hitl_learning_engine.py`：
    - 定义常量 `LEARNING_UPDATES_PATH = artifacts/learning_updates.json`。
    - 实现函数 `apply_hitl_learning(hitl_patch, dq_report, parser_strategy, chunk_policy)`：
      - 根据 `patch_type` 生成确定性的 `LearningUpdate` 列表：
        - `ocr_cell` / `table_cell` → kind=`parser_strategy_prior`。
        - `chunk_boundary` → kind=`chunk_policy`。
        - `numeric_cell` → kind=`numeric_first_weight`。
      - 将汇总结果（包含 `job_id`、`patch_type`、`updates[]`）写入 `artifacts/learning_updates.json`，不直接修改在线配置。
  - 新增测试 `tests/test_hitl_learning_loop.py`：
    - `test_hitl_learning_generates_updates`：对 `ocr_cell` patch 调用 `apply_hitl_learning`，断言：
      - 生成的 `learning_updates.json` 存在。
      - 返回的 `summary["updates"]` 非空，且包含 `kind="parser_strategy_prior"`。
    - `test_hitl_learning_no_updates_fails`：对未知 `patch_type` 调用 `apply_hitl_learning`，断言 `updates` 为空，作为“patch 未产生学习更新”的 FAIL 场景。
- **对应要求**
  - Phase 8 · P5-1：HITL Learning Loop，HITL patch 不仅修当前结果，还要产生可审计的策略更新信号。
- **是否属于降级**
  - NO：仅生成学习更新文件，不改动核心执行路径或现有策略；后续可由独立进程/操作将这些更新应用回配置。
- **风险评估**
  - low：逻辑简单、纯增加能力，已由单测保护。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `backend/learning/*` 与 `tests/test_hitl_learning_loop.py`。

---

## 2026-Phase8-010 — Eval Coverage Matrix（P6-1）

- **修改文件**
  - `backend/eval/__init__.py`
  - `backend/eval/coverage_matrix.py`
  - `backend/eval/eval_runner.py`
  - `tests/test_eval_coverage_matrix.py`
- **变更内容**
  - 新增 Eval Coverage Matrix 模块 `backend/eval/coverage_matrix.py`：
    - 定义 `build_coverage_matrix(eval_report: dict) -> dict`，根据 `eval_report["metrics"]` 中是否存在固定路径判断覆盖情况：
      - `offline.parse.ocr`
      - `offline.chunk.stability`
      - `online.retrieval.recall@k`
      - `online.rerank`
      - `online.verification.coverage`
      - `hitl.fix_rate`
      - `cost.budget`
      - `latency.slo`
    - 规则：路径存在 → `{"covered": True}`，否则 `{"covered": False}`。
  - 新增 Eval Runner 帮助模块 `backend/eval/eval_runner.py`：
    - 提供 `write_eval_report(eval_report: dict, path: str) -> str`：
      - 自动调用 `build_coverage_matrix` 生成 `coverage_matrix`。
      - 将其附加到 `eval_report["coverage_matrix"]` 并写入指定 JSON 文件路径。
  - 新增测试 `tests/test_eval_coverage_matrix.py`：
    - `test_eval_coverage_matrix_pass`：构造包含多项 metrics 的 `eval_report`，断言相应 coverage 项为 `True`。
    - `test_eval_coverage_matrix_missing_metrics`：构造缺失大部分 metrics 的 `eval_report`，断言对应 coverage 项为 `False`，并验证 `write_eval_report` 写出的文件中带有 `coverage_matrix` 字段。
- **对应要求**
  - Phase 8 · P6-1：Eval Coverage Matrix，系统必须自动知道哪些 Pipeline / Component / Metric 被覆盖，哪些没有。
- **是否属于降级**
  - NO：仅新增覆盖矩阵与写入逻辑，不更改现有评测行为。
- **风险评估**
  - low：覆盖矩阵基于固定路径检查，后续在扩展 metrics 结构时需同步更新路径映射。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `backend/eval/*` 与 `tests/test_eval_coverage_matrix.py`。

---

## 2026-Phase8-011 — Eval → Learning Signal Bridge（P6-2）

- **修改文件**
  - `backend/eval/eval_signal_generator.py`
  - `tests/test_eval_signal_generation.py`
- **变更内容**
  - 新增 Eval 学习信号生成模块 `backend/eval/eval_signal_generator.py`：
    - 从 `configs/release_gate.yaml` 中加载 Gate 阈值（如存在），否则使用安全默认值。
    - 实现 `generate_eval_signals(eval_report, coverage_matrix)`：
      - 当 `online.numeric.numeric_mismatch_rate > numeric_mismatch_threshold` 时，生成：
        `{"type":"numeric_mismatch_rate_high","action_hint":"increase_numeric_first_weight"}`。
      - 当 `online.retrieval.recall@5 < gate.online.retrieval_recall_at_5_min` 时，生成：
        `{"type":"retrieval_recall_low","action_hint":"increase_hybrid_weight"}`。
      - 当 `hitl.fix_rate < hitl.fix_rate_threshold` 时，生成：
        `{"type":"hitl_fix_rate_low","action_hint":"improve_offline_quality_or_routing"}`。
      - 将所有 signals 以 `{"signals":[...]}` 写入 `artifacts/eval_learning_signals.json`。
  - 新增测试 `tests/test_eval_signal_generation.py`：
    - `test_eval_signal_generated_for_abnormal_metrics`：构造异常指标（高 numeric_mismatch_rate、低 recall@5、低 fix_rate），断言三类 signal 均生成。
    - `test_eval_signal_not_generated_when_metrics_normal`：构造全部在阈值内的指标，断言返回 `signals == []`。
- **对应要求**
  - Phase 8 · P6-2：Eval → Learning Signal Bridge，评测必须产生结构化的学习信号，而不是只做 Gate。
- **是否属于降级**
  - NO：仅新增独立信号生成模块与测试，不改变现有 Gate 行为。
- **风险评估**
  - low：逻辑简单，完全可追踪，输出为只读 artifacts。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 `backend/eval/eval_signal_generator.py` 与对应测试。

---

## 2026-Phase8-012 — Use-Case Eval Suite（P6-3）

- **修改文件**
  - `eval/use_cases/finance_annual_fee.json`
  - `eval/use_cases/finance_cashback.json`
  - `eval/use_cases/finance_terms_conflict.json`
  - `backend/eval/use_case_runner.py`
  - `tests/test_use_case_eval.py`
- **变更内容**
  - 新增金融 use-case 定义（业务场景）：
    - `finance_annual_fee.json`、`finance_cashback.json`、`finance_terms_conflict.json`，每个文件定义：
      - `scenario`、`question`、`expected_fields` 与 `evaluation_rules`（字段规则 + citation 要求）。
  - 新增 Use-Case 执行器 `backend/eval/use_case_runner.py`：
    - 加载 `eval/use_cases/*.json`，按 `scenario` 键索引。
    - 实现 `evaluate_use_cases(answer_bundle) -> dict`：
      - `answer_bundle` 中每个场景包含：
        `{"fields": {...}, "citations": [...]}`。
      - 不使用文本相似度，只基于：
        - 字段存在性（`must_exist`）。
        - 数值一致性（`numeric_exact_or_tolerance`，内置 1% 或 0.01 容差）。
        - citation 存在（`citation: required`）。
      - 返回 `{"scenario_name": "pass" | "fail"}`。
  - 新增测试 `tests/test_use_case_eval.py`：
    - `test_use_case_eval_pass`：提供完整字段 + 正确数值 + citation 的 answer_bundle，断言 3 个场景均 `pass`。
    - `test_use_case_eval_fail_missing_field_or_citation`：缺字段 / 数值错误 / 无 citation 时，断言 3 个场景均 `fail`。
- **对应要求**
  - Phase 8 · P6-3：Use-Case Eval Suite，基于业务字段与数值/条款正确性判断，而非语言相似度。
- **是否属于降级**
  - NO：新增独立 use-case 评测能力与测试，不改动现有通用 eval 流程。
- **风险评估**
  - low：仅引入金融示例场景，逻辑可扩展至其他行业。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 use-case 定义、执行器与测试。

---

## 2026-Phase8-013 — Continuous Evaluation Scheduler（P6-4）

- **修改文件**
  - `configs/continuous_eval.yaml`
  - `backend/eval/continuous_eval_scheduler.py`
  - `tests/test_continuous_eval.py`
- **变更内容**
  - 新增 Continuous Eval 配置 `configs/continuous_eval.yaml`：
    - `sampling_rate`、`max_daily_eval`、`shadow_mode` 三个参数用于控制线上抽样评测行为。
  - 新增 Continuous Eval 调度器 `backend/eval/continuous_eval_scheduler.py`：
    - 加载配置 `continuous_eval.yaml`，基于 `sampling_rate` 与 `max_daily_eval` 对请求 ID 进行确定性 hash 抽样。
    - 实现 `schedule_continuous_eval(request_ids)`：
      - 返回被选中的 `request_id` 列表。
      - 将选中 ID 以 `{"request_id": "...", "scheduled": true}` 形式追加写入 `artifacts/continuous_eval_history.jsonl`。
  - 新增测试 `tests/test_continuous_eval.py`：
    - `test_continuous_eval_sampling_selects_requests`：`sampling_rate=0.5`、`max_daily_eval=10` 时，断言：
      - 至少 1 个请求被选中；
      - 选中数量 ≤ 10；
      - `continuous_eval_history.jsonl` 被写入。
    - `test_continuous_eval_disabled_when_sampling_zero`：`sampling_rate=0.0` 时，断言：
      - 不应选中任何请求（`selected == []`）。
- **对应要求**
  - Phase 8 · P6-4：Continuous Evaluation，对线上请求进行抽样评测并记录历史，使系统在部署后仍具备质量可观测能力。
- **是否属于降级**
  - NO：仅增加调度与配置，不改变线上请求主路径或 Gate 行为。
- **风险评估**
  - low：调度策略确定性且受配置控制，可按需关闭/调整采样。
- **回滚方式**
  - 使用 `git revert` 回滚本次变更，删除 Continuous Eval 配置、调度器与测试。


