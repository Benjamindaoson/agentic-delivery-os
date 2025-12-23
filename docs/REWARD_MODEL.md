# Reward Model (Semantic + Structural)

## 1. Semantic Task Success
- File: `learning/semantic_task_success.py`
- Inputs:
  - `quality_score` (0~1)
  - `grounding_score` (0~1)
  - `cost_efficiency` (1 - cost/budget, 0~1)
  - `user_intent_match` (0~1)
- Weights (default): quality 0.35, grounding 0.25, cost 0.20, intent 0.20
- Output: `reward ∈ [0,1]`
- Traceability: each computation appended to `artifacts/reward_trace.json` with full breakdown.

## 2. Structural Reward (DAG-Level)
- File: `learning/structural_learning.py` (`StructuralRewardComputer`)
- Components:
  - task_success, quality_score, cost_efficiency, latency_efficiency
  - minimal_structure_bonus, adaptation_bonus
- Output: `StructuralReward.total_reward`
- Credit Assignment: `StructuralCreditAssigner` distributes credit to nodes/edges/agents.
- Artifacts:
  - `artifacts/learning/structural/structural_policy.json`
  - `artifacts/learning/structural/dag_preference_stats.json`
  - `artifacts/structural_learning_report.json`

## 3. Unified Reward Usage
- Bandit / Offline RL / Meta-Policy now implement `AbstractPolicy.compute_reward` via `semantic_task_success`.
- Exploration Engine combines:
  - Semantic reward
  - Structural reward (when DAG features available)
  - Logged to `artifacts/exploration/rewards/{run_id}.json`

## 4. Budget & Governance
- Cost efficiency derived from actual cost vs budget.
- Governance cost guardrails enforce blocking/soft warnings.
- Rewards remain audit-ready via artifacts.

## 5. Traceability Guarantees
- `artifacts/reward_trace.json` — semantic reward history
- `artifacts/exploration/rewards/*.json` — exploration rewards
- `artifacts/structural_learning_report.json` — structural learning summary
- All reward artifacts include timestamps and inputs for replay.

