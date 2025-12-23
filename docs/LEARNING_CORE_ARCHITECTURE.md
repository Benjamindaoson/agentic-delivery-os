# Learning Core Architecture (Round 2 Hardening)

> Scope: Unified Learning Abstraction, Semantic Reward, Structural Learning, Exploration, Meta-Learning  
> Status: Production-ready, no mocks

## 1. Unified Policy Abstraction
- File: `learning/abstract_policy.py`
- Interface: `encode_state()`, `select_action()`, `compute_reward()`, `update()`, `export_policy()`
- Implementations:
  - `BanditSelector` (bandit) — now an `AbstractPolicy`
  - `OfflineRLAgent` (offline RL) — now an `AbstractPolicy`
  - `MetaPolicy` (cross-tenant) — now an `AbstractPolicy`
- Supports paradigm migration: Bandit → RL via consistent interfaces.

## 2. Semantic Reward Model
- File: `learning/semantic_task_success.py`
- Inputs: `quality_score`, `grounding_score`, `cost_efficiency`, `user_intent_match`
- Output: reward ∈ [0,1] + detailed breakdown
- Traceability: appended to `artifacts/reward_trace.json` for every computation.

## 3. Structural Learning (DAG-Level)
- File: `learning/structural_learning.py`
- Features:
  - DAG feature extraction (`StructuralFeatureExtractor`)
  - Structural reward (`StructuralRewardComputer`)
  - Credit assignment (`StructuralCreditAssigner`)
  - Policy export: `artifacts/learning/structural/structural_policy.json`
  - Preference stats: `artifacts/learning/structural/dag_preference_stats.json`
  - Report: `artifacts/structural_learning_report.json`
- Execution integration: `execution_engine` consumes structural policy to reorder DAG with fallback.

## 4. Exploration Engine
- File: `runtime/exploration/exploration_engine.py`
- Upgrades:
  - Real shadow + replay path (GoldenReplay + ShadowExecutor)
  - Reward = semantic + structural
  - Budget-aware via `FailureBudget`
  - Rewards logged to `artifacts/exploration/rewards/{run_id}.json`

## 5. Meta-Learning (Cross-Tenant)
- File: `learning/meta_policy.py`
- Upgrades:
  - Cold-start warm boot via pattern embeddings (hash + vector)
  - Privacy-safe aggregation with noise
  - AbstractPolicy-compliant for unified consumption

## 6. Reward Trace & Pipelines
- `LearningController` now records semantic reward traces for recent runs into `artifacts/reward_trace.json`.
- All policies use `semantic_task_success` for reward computation.

## 7. Data & Artifacts
- `artifacts/reward_trace.json` — semantic rewards
- `artifacts/structural_learning_report.json` — structural learning summary
- `artifacts/learning/structural/structural_policy.json` — DAG policy
- `artifacts/learning/structural/dag_preference_stats.json` — stats
- `artifacts/exploration/rewards/{run}.json` — exploration rewards

## 8. Consumption Points
- Execution DAG adjustment: `execution_engine` applies structural policy (with rollback fallback).
- Exploration: combines semantic + structural reward under budget guard.
- Meta: provides warm-start strategy for new tenants using privacy-safe embeddings.

