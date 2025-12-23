# L5.5 Exploration (Engineering) Whitepaper

## 模块图
- Exploration Engine (`runtime/exploration/exploration_engine.py`)
- Failure Budget (`runtime/exploration/failure_budget.py`)
- Discovery Reward (`runtime/exploration/discovery_reward.py`)
- Strategy Genome & Candidate Generator (`runtime/exploration/strategy_genome.py`, `candidate_generator.py`)
- Policy Registry/Packager (`runtime/policy/policy_registry.py`, `policy_packager.py`)
- Shadow Executor (`runtime/shadow/shadow_executor.py`)
- Golden Replay Suite + Regression Gate (`runtime/eval/golden_replay_suite.py`, `policy_regression_runner.py`)
- Strategy Selector (bandit hook) (`runtime/strategy/strategy_selector.py`)
- Decision Attribution / KPI Aggregator (existing, extended) (`runtime/analysis/decision_attributor.py`, `runtime/metrics/policy_kpi_aggregator.py`)
- Signal Collector hooks (`runtime/learning/signal_collector.py`)

## Artifact 列表（均含 schema_version, timestamp, inputs_hash）
- Exploration
  - `artifacts/exploration/decisions/{run_id}.json`
  - `artifacts/exploration/budget_state.json`
  - `artifacts/exploration/rewards/{run_id}.json`
- Policy
  - `artifacts/policy/candidates/{candidate_id}.json`
  - `artifacts/policy/registry.json`
- Eval / Shadow / Regression
  - `artifacts/eval/shadow_diff/{run_id}.json`
  - `artifacts/eval/golden_replay_report_{candidate_id}.json`
  - `artifacts/policy_regression_report.json`
- Attribution / Strategy
  - `artifacts/attribution/{run_id}.json` (alias of attributions)
  - `artifacts/strategy/strategy_decisions.json`
  - `artifacts/policy_kpis.json`

## 数据流（受控探索）
1. Run 完成 → SignalCollector 可选触发 `ExplorationEngine.maybe_explore(...)`（shadow-only）
2. Exploration 决策输出 decision artifact，检查 budget（failures/cost/latency）
3. CandidateGenerator 基于 genome 变异生成 candidate artifact → 注册到 PolicyRegistry
4. ShadowExecutor 对 candidate 进行影子跑，产出 `shadow_diff`
5. GoldenReplaySuite + PolicyRegressionRunner 对 candidate 做回放和退化阻断
6. DiscoveryReward 计算奖励 → 写 reward artifact
7. StrategySelector (bandit) 可用于选择探索/稳定策略（shadow-only）
8. LearningController 读取 attribution/KPI/regression/feedback 供训练（未改主控制流）

## 验收条件对照
- 删除 `runtime/exploration/`，主流程仍可运行（仅失去探索能力）
- exploration 决策、预算、奖励、候选、评测均有 JSON artifact
- candidate 必须经过 shadow + replay + gate，不直接上线
- 预算耗尽 → exploration 决策 explore=false，并写 hard_stop
- Regression 退化 → PolicyRegressionRunner 生成 blocking_reasons 并 safe_to_rollout=false
- Tests 覆盖 5 个核心用例并全绿（见下）
- 文档提供 replay/diff/audit 路径

## 如何运行测试
```bash
pytest tests/test_l5_5_exploration.py -v --tb=short
pytest tests/ -v --tb=short -q --ignore=tests/test_backend_api.py
```

## 如何手动触发探索（示例）
```python
from runtime.exploration.exploration_engine import ExplorationEngine
engine = ExplorationEngine()
decision = asyncio.run(engine.maybe_explore(
    run_id="demo_run",
    run_signals={"run_success": False, "pattern_is_new": True, "retrieval_policy_id": "basic_v1"},
    attribution={"primary_cause": "RETRIEVAL_MISS"},
    policy_kpis={"success_rate": 0.6},
))
print(decision)
```

## Replay / Diff / Audit
- Replay：使用 `inputs_hash` + saved artifacts（shadow_diff, golden_replay_report）重放候选评测
- Diff：对比 `policy/candidates/*.json` 或 `strategy_decisions.json` 版本差异
- Audit：依据 `blocking_reasons`, `decision.trigger.reason_codes`, `reward.components` 快速定位 gate 结果



