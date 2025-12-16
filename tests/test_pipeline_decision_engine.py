from pipeline_decision import DocumentProfile, InputContext, decide_pipeline
from pipeline_decision.bandit import LinUCB


def test_low_risk_path(tmp_path):
    ctx = InputContext(
        industry="education",
        task_type="qa",
        document_profile=DocumentProfile(language="en"),
        user_preference="speed",
        decision_impact="informational",
    )
    result = decide_pipeline(ctx, bandit_state_path=str(tmp_path / "bandit_low.json"))
    assert result.risk_level == "LOW"
    assert result.chosen_plan_id == "fast_path"
    assert result.questions_to_ask == []


def test_medium_risk_path(tmp_path):
    ctx = InputContext(
        industry="public_sector",
        task_type="compliance",
        document_profile=DocumentProfile(contains_dense_tables=True, language="en"),
        user_preference="quality",
        decision_impact="operational",
    )
    result = decide_pipeline(ctx, bandit_state_path=str(tmp_path / "bandit_med.json"))
    assert result.risk_level == "MEDIUM"
    assert result.chosen_plan_id == "balanced"


def test_high_risk_path(tmp_path):
    ctx = InputContext(
        industry="finance",
        task_type="compliance",
        document_profile=DocumentProfile(
            is_scanned=True, contains_dense_tables=True, has_handwriting=True, language="fr"
        ),
        user_preference="quality",
        decision_impact="regulatory",
    )
    result = decide_pipeline(ctx, bandit_state_path=str(tmp_path / "bandit_high.json"))
    assert result.risk_level == "HIGH"
    assert result.chosen_plan_id == "high_fidelity"


def test_uncertainty_triggers_questions(tmp_path):
    ctx = InputContext(
        industry="public_sector",
        task_type="research",
        document_profile=DocumentProfile(contains_dense_tables=True, language="es"),
        user_preference="cost",
        decision_impact="operational",
    )
    result = decide_pipeline(ctx, bandit_state_path=str(tmp_path / "bandit_uncertain.json"))
    assert 0 < len(result.questions_to_ask) <= 3


def test_high_risk_missing_field_prompts_required_question(tmp_path):
    ctx = InputContext(
        industry="finance",
        task_type="compliance",
        document_profile=DocumentProfile(
            is_scanned=True, contains_dense_tables=True, has_handwriting=True, language="fr", data_sensitivity=""
        ),
        user_preference="quality",
        decision_impact="regulatory",
    )
    result = decide_pipeline(ctx, bandit_state_path=str(tmp_path / "bandit_missing.json"))
    ids = [q["id"] for q in result.questions_to_ask]
    assert "data_sensitivity" in ids


def test_bandit_update_changes_preference(tmp_path):
    state_path = tmp_path / "bandit_state.json"
    arms = ["fast_path", "balanced"]
    bandit = LinUCB(arms=arms, alpha=0.5, state_path=state_path, context_dim=5)
    x = [1.0] * 5
    bandit.update(x, "balanced", reward=5.0)
    bandit.update(x, "fast_path", reward=-1.0)
    second_choice, _ = bandit.select_arm(x)
    assert second_choice == "balanced"
    assert state_path.exists()

