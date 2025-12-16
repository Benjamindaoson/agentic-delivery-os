# Pipeline Decision Engine

This module upgrades the previous rules-based selector into an algorithmic decision engine that combines cost-sensitive risk scoring, contextual bandits (LinUCB), and active-learning question selection. The unified output is a `PipelineDecisionResult`:

```python
{
  "risk_score": float,
  "risk_level": "LOW|MEDIUM|HIGH",
  "chosen_plan_id": str,
  "plan": {...},
  "confidence": float,
  "questions_to_ask": [ {"id":..., "text":..., "score":...}, ... ],
  "rationale": ["feature_1: 3.2", ...],
  "debug": {"risk":..., "bandit":..., "questions":...}
}
```

## Cost-Sensitive Risk Scoring

*Problem definition*: `risk_score` represents expected cost of error (not probability) given context.

*Feature construction*: `pipeline_decision.risk.featurize` builds a vector using `InputContext` and `DocumentProfile` (industry priors, task/impact risk, document complexity, handwriting, dense tables, language, and user preference signals).

*Model*: A quadratic linear form with optional interactions loaded from `config/pipeline_decision.yaml`:

```
score = clip(Σ w_i f_i + Σ w_ij f_i f_j, 0, 100)
expected_cost = score * (1 + avg(cost_fn, cost_fp)/20) + cost_critical * doc_complexity/10
```

Thresholds in the same config map scores to LOW/MEDIUM/HIGH. The rationale surfaces the top feature contributions for explainability.

## Contextual Bandit Policy Selector (LinUCB)

*Problem definition*: choose one of the pipeline plans (arms) to maximize long-term reward under context `x`.

`pipeline_decision.bandit.LinUCB` implements selection and online updates with persistence to `artifacts/bandit_state.json`. For context vector dimensions, we use `[1, risk_score/100, doc_complexity/5, language_non_en, pref_quality]`.

*Cold start*: if no persisted state is found, the selector falls back to the risk-aligned plan while still returning bandit debug information so the state can be initialized later.

*Debug surface*: top-2 UCB scores, exploration vs. exploitation breakdown, and gap for uncertainty-driven behaviors.

## Active Learning Question Selector

*Problem definition*: when confidence is low, plans are uncertain, or key high-risk fields are missing, ask the smallest set of questions that reduces decision uncertainty.

`pipeline_decision.questions.select_questions` uses uncertainty sampling with impact weighting:

```
score(question) = impact_weight * (1 - confidence + bandit_uncertainty)
```

Questions are defined in `config/pipeline_decision.yaml` with `id`, `text`, `related_features`, and `expected_impact_weight`. If `risk_level == HIGH` and a question is marked `required_for_high_risk` with missing features, it is force-boosted into the top list. Returned questions are sorted by score and limited to three.

## Confidence Formula

Confidence reflects distance from risk thresholds and is penalized by small bandit gaps:

* LOW region: `(medium_threshold - score) / medium_threshold`
* MEDIUM region: min distance to thresholds normalized by `(high - medium)`
* HIGH region: `(score - high_threshold) / (100 - high_threshold)`
* Penalty: subtract `max(0, 0.3 - bandit_gap)` to reflect exploration uncertainty.

## Updating the Bandit

Call `decide_pipeline(..., reward=<observed_reward>)` to update LinUCB after observing a reward (using the weights from the config to compute the scalar). State is persisted automatically.

## Cold Start and End-to-End Flow

1. Risk model scores context and sets risk level.
2. LinUCB selects a plan (or falls back if no state), emitting debug with UCB scores.
3. Confidence is derived from risk distance to thresholds and bandit gap.
4. Active-learning selector asks targeted questions when uncertainty is high or key fields are missing.
5. The engine returns the structured `PipelineDecisionResult` used by callers and tests.

## Example

```bash
python -c "from pipeline_decision import decide_pipeline, InputContext, DocumentProfile; print(decide_pipeline(InputContext(industry='finance', task_type='compliance', document_profile=DocumentProfile(is_scanned=True, contains_dense_tables=True, language='fr', has_handwriting=True), user_preference='quality', decision_impact='regulatory')))
```

The command emits a dictionary-like decision containing `risk_score`, `chosen_plan`, `confidence`, and `questions_to_ask`.

