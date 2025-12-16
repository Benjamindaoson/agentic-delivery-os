import os

from pipeline_decision import DocumentProfile, InputContext, decide_pipeline
from pipeline_decision.bandit import LinUCBPolicy
from pipeline_decision.engine import _feature_vector, load_config
from pipeline_decision.risk import RiskModel

CONFIG_PATH = "config/pipeline_decision.yaml"


def test_low_risk_plan_selection(tmp_path):
    context = InputContext(
        industry="education",
        task_type="qa",
        document_profile=DocumentProfile(language="en", contains_dense_tables=False, is_scanned=False, has_handwriting=False),
        user_preference="speed",
        decision_impact="informational",
    )
    result = decide_pipeline(context, config_path=CONFIG_PATH, bandit_state_path=str(tmp_path / "bandit.json"))
    assert result.risk_level == "LOW"
    assert result.chosen_plan_id == "fast_low"
    assert result.questions_to_ask == []


def test_medium_risk_plan_selection(tmp_path):
    context = InputContext(
        industry="public_sector",
        task_type="research",
        document_profile=DocumentProfile(is_scanned=False, contains_dense_tables=False, language="en"),
        user_preference="quality",
        decision_impact="operational",
    )
    result = decide_pipeline(context, config_path=CONFIG_PATH, bandit_state_path=str(tmp_path / "bandit.json"))
    assert result.risk_level == "MED"
    assert result.chosen_plan_id == "balanced_med"


def test_high_risk_plan_selection(tmp_path):
    context = InputContext(
        industry="finance",
        task_type="compliance",
        document_profile=DocumentProfile(is_scanned=True, contains_dense_tables=True, has_handwriting=True, language="fr"),
        user_preference="quality",
        decision_impact="regulatory",
    )
    result = decide_pipeline(context, config_path=CONFIG_PATH, bandit_state_path=str(tmp_path / "bandit.json"))
    assert result.risk_level == "HIGH"
    assert result.chosen_plan_id == "guardrail_high"


def test_uncertainty_triggers_questions(tmp_path):
    # sparse context to keep confidence low and trigger questions
    context = InputContext(
        industry="",
        task_type="",
        document_profile=DocumentProfile(language="fr", contains_dense_tables=True),
        user_preference="",
        decision_impact="",
    )
    result = decide_pipeline(context, config_path=CONFIG_PATH, bandit_state_path=str(tmp_path / "bandit.json"))
    assert result.confidence < 0.7
    assert 1 <= len(result.questions_to_ask) <= 3


def test_high_risk_missing_fields_requires_questions(tmp_path):
    context = InputContext(
        industry="finance",
        task_type="compliance",
        document_profile=DocumentProfile(is_scanned=None, contains_dense_tables=True, has_handwriting=True, language=None),
        user_preference="quality",
        decision_impact="regulatory",
    )
    result = decide_pipeline(context, config_path=CONFIG_PATH, bandit_state_path=str(tmp_path / "bandit.json"))
    ids = [q["id"] for q in result.questions_to_ask]
    assert result.risk_level == "HIGH"
    assert "q_scan_quality" in ids or "q_tables" in ids or "q_handwriting" in ids


def test_bandit_update_biases_choice(tmp_path):
    config = load_config(CONFIG_PATH)
    risk_model = RiskModel(config)
    context = InputContext(
        industry="finance",
        task_type="compliance",
        document_profile=DocumentProfile(is_scanned=True, contains_dense_tables=True, has_handwriting=False, language="en"),
        decision_impact="regulatory",
    )
    features = risk_model.featurize(context, context.document_profile)
    feature_vector = _feature_vector(features, config)
    state_path = str(tmp_path / "bandit_state.json")
    policy = LinUCBPolicy(plans=config["plans"], alpha=1.0, state_path=state_path)
    policy.update(feature_vector, "balanced_med", reward=2.5)
    policy.update(feature_vector, "fast_low", reward=0.1)
    chosen, debug = policy.select_arm(feature_vector, "MED", 60)
    assert debug.used_bandit is True
    assert chosen == "balanced_med"
