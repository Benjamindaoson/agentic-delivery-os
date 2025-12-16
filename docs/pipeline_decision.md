# Pipeline Decision Engine

This document explains how the decision engine turns contextual signals into a pipeline plan using three coordinated algorithms: cost-sensitive risk scoring, a LinUCB contextual bandit, and an active-learning question selector.

## Inputs
- `InputContext`: industry, task_type, decision_impact, user_preference, optional DocumentProfile.
- `DocumentProfile`: is_scanned, contains_dense_tables, has_handwriting, language (all optional to allow "unknown").

## Risk scoring (cost-sensitive)
- Featurize context+profile into indicator features (industry_x, task_y, doc_scanned, language_non_en, etc.).
- Compute linear + interaction contributions using weights from `config/pipeline_decision.yaml` and apply industry priors.
- Convert to *expected cost of error* by scaling with the asymmetric `cost_matrix` (false_negative vs false_positive vs catastrophic).
- Clip to `[0,100]` and map to `risk_level` with `thresholds.low/medium/high`.
- Confidence = `1 - distance_to_nearest_threshold/100`.
- Rationale lists top feature contributions.

## Bandit policy selector (LinUCB)
- Context vector = deterministic ordering of features defined by the config weights.
- If `bandit_state.json` is missing: **cold start** picks the plan whose `risk_level` matches and whose `target_score` is closest to the risk score. Bandit debug still returned for continuity.
- If state exists: LinUCB computes `p = theta^T x + alpha * sqrt(x^T A^-1 x)` per plan, chooses the max, and records top-2 scores plus exploration term.
- State (A,b per plan) is persisted to `artifacts/bandit_state.json` by `update`.
- Reward model left to caller; example combines quality/cost/latency/risk/rollback as a single scalar.

## Active-learning question selector
- Triggered when confidence is below `question_conf_threshold`, when high-risk has missing related features, or when bandit margin between top-2 plans is small.
- Score per question = `expected_impact_weight * (uncertainty + bandit_uncertainty)` plus a bonus if required-for-high-risk and the related feature is missing.
- Returns up to 3 questions sorted by score.

## Confidence aggregation
`final_confidence = 0.6 * risk_confidence + 0.4 * bandit_confidence`, where bandit confidence is the normalized margin between the top two UCB scores.

## Outputs
`PipelineDecisionResult` is a dict-like object with:
- `risk_score`, `risk_level`
- `chosen_plan_id`, `plan` (strategies from config)
- `confidence`
- `questions_to_ask`
- `rationale` (top feature contributions, plan choice rationale)
- `debug` (risk contributions, bandit scores, question scores, feature vector)

## Updating bandit online
```python
from pipeline_decision import decide_pipeline, InputContext, DocumentProfile
from pipeline_decision.bandit import LinUCBPolicy

context = InputContext(industry="finance", task_type="compliance")
result = decide_pipeline(context)
# Suppose we observed a reward from execution
reward = 1.0
from pipeline_decision.engine import load_config
config = load_config("config/pipeline_decision.yaml")
policy = LinUCBPolicy(plans=[{"id": p["id"], "risk_level": p["risk_level"]} for p in config["plans"]])
policy.update(result.debug["feature_vector"], result.chosen_plan_id, reward)
```

## Minimal runnable example
```bash
python -c "from pipeline_decision import decide_pipeline, InputContext, DocumentProfile;print(decide_pipeline(InputContext(industry='finance', task_type='compliance', document_profile=DocumentProfile(is_scanned=True, contains_dense_tables=True))))"
```
