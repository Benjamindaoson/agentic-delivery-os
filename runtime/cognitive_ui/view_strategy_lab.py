"""
Strategy Lab View: Design and review custom strategies
"""
import streamlit as st
import json
import os
from typing import Dict, Any
from datetime import datetime
from runtime.cognitive_ui.components import (
    render_json_editor,
    render_review_result
)


def validate_strategy(strategy_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal strategy validation (rule-based)
    
    Rules:
    - No tool calls allowed
    - Only affect: plan_selector, exploration, cost thresholds, risk thresholds
    - Must have a valid name and version
    
    Returns:
        {
            "verdict": "approve" | "revise" | "reject",
            "reason": str,
            "issues": List[str]
        }
    """
    issues = []
    
    # Check required fields
    if "name" not in strategy_spec:
        issues.append("Missing required field: 'name'")
    
    if "version" not in strategy_spec:
        issues.append("Missing required field: 'version'")
    
    # Check for prohibited fields
    if "tool_calls" in strategy_spec:
        issues.append("Prohibited field: 'tool_calls' (strategies cannot directly call tools)")
    
    if "code_execution" in strategy_spec:
        issues.append("Prohibited field: 'code_execution' (strategies cannot execute code)")
    
    # Check allowed fields
    allowed_fields = {
        "name", "version", "description", "author",
        "plan_selector", "exploration", "cost_thresholds", "risk_thresholds",
        "policy_params", "metadata"
    }
    
    for field in strategy_spec.keys():
        if field not in allowed_fields:
            issues.append(f"Unknown field: '{field}' (may not be supported)")
    
    # Validate cost thresholds if present
    if "cost_thresholds" in strategy_spec:
        cost_thresholds = strategy_spec["cost_thresholds"]
        if not isinstance(cost_thresholds, dict):
            issues.append("'cost_thresholds' must be a dictionary")
        else:
            for key in ["alert_threshold", "degrade_threshold", "terminate_threshold"]:
                if key in cost_thresholds:
                    value = cost_thresholds[key]
                    if not isinstance(value, (int, float)) or value < 0 or value > 1:
                        issues.append(f"'{key}' must be a number between 0 and 1")
    
    # Validate risk thresholds if present
    if "risk_thresholds" in strategy_spec:
        risk_thresholds = strategy_spec["risk_thresholds"]
        if not isinstance(risk_thresholds, dict):
            issues.append("'risk_thresholds' must be a dictionary")
    
    # Determine verdict
    if len(issues) == 0:
        verdict = "approve"
        reason = "Strategy passed all validation checks"
    elif any("Prohibited" in issue for issue in issues):
        verdict = "reject"
        reason = "Strategy contains prohibited fields or operations"
    else:
        verdict = "revise"
        reason = f"Strategy has {len(issues)} issue(s) that need to be fixed"
    
    return {
        "verdict": verdict,
        "reason": reason,
        "issues": issues
    }


def save_review_artifact(strategy_spec: Dict[str, Any], review_result: Dict[str, Any]) -> str:
    """
    Save strategy review artifact
    
    Returns:
        Path to saved artifact
    """
    review_dir = "artifacts/strategy_reviews"
    os.makedirs(review_dir, exist_ok=True)
    
    strategy_id = f"{strategy_spec.get('name', 'unnamed')}_{strategy_spec.get('version', '1.0')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    artifact = {
        "strategy_id": strategy_id,
        "strategy_spec": strategy_spec,
        "review_result": review_result,
        "reviewed_at": datetime.now().isoformat()
    }
    
    artifact_path = os.path.join(review_dir, f"{strategy_id}.json")
    
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    
    return artifact_path


def render_strategy_lab_view():
    """
    Render the Strategy Lab view page
    
    Features:
    - Edit strategy spec (JSON)
    - Review strategy (local validation)
    - Save review artifact
    """
    st.title("🧪 Strategy Lab")
    st.markdown("Design and review custom strategies. Strategies define system behavior parameters.")
    
    # Info box
    with st.expander("ℹ️ What is a Strategy?", expanded=False):
        st.markdown("""
        A **Strategy** is a configuration that affects system behavior without direct code execution.
        
        **Allowed Fields:**
        - `name`: Strategy name (required)
        - `version`: Version string (required)
        - `description`: Human-readable description
        - `plan_selector`: Plan selection parameters
        - `exploration`: Exploration rate and budget
        - `cost_thresholds`: Alert/degrade/terminate thresholds (0.0-1.0)
        - `risk_thresholds`: Risk tolerance levels
        - `policy_params`: Policy-specific parameters
        
        **Prohibited:**
        - `tool_calls`: Strategies cannot directly call tools
        - `code_execution`: Strategies cannot execute arbitrary code
        
        **Example:**
        ```json
        {
          "name": "conservative_strategy",
          "version": "1.0",
          "description": "Low-risk, cost-conscious strategy",
          "cost_thresholds": {
            "alert_threshold": 0.7,
            "degrade_threshold": 0.85,
            "terminate_threshold": 0.95
          },
          "exploration": {
            "enabled": false
          }
        }
        ```
        """)
    
    # Default strategy template
    default_strategy = {
        "name": "custom_strategy",
        "version": "1.0",
        "description": "Custom strategy template",
        "cost_thresholds": {
            "alert_threshold": 0.8,
            "degrade_threshold": 0.9,
            "terminate_threshold": 1.0
        },
        "risk_thresholds": {
            "acceptable_risk": "medium"
        },
        "exploration": {
            "enabled": True,
            "exploration_rate": 0.1
        },
        "metadata": {
            "author": "user",
            "created_at": datetime.now().isoformat()
        }
    }
    
    # Load existing strategy if in session state
    if "current_strategy" not in st.session_state:
        st.session_state.current_strategy = default_strategy
    
    # Strategy editor
    st.header("✏️ Edit Strategy")
    
    edited_text = render_json_editor(
        label="Strategy Specification (JSON)",
        initial_value=st.session_state.current_strategy,
        key="strategy_editor"
    )
    
    # Parse button
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Reset to Template", key="reset_strategy"):
            st.session_state.current_strategy = default_strategy
            st.experimental_rerun()
    
    with col2:
        parse_clicked = st.button("✅ Parse JSON", key="parse_strategy")
    
    with col3:
        review_clicked = st.button("🔍 Review Strategy", key="review_strategy", type="primary")
    
    # Parse JSON
    parsed_strategy = None
    parse_error = None
    
    if parse_clicked or review_clicked:
        try:
            parsed_strategy = json.loads(edited_text)
            st.session_state.current_strategy = parsed_strategy
            st.success("✅ JSON parsed successfully")
        except json.JSONDecodeError as e:
            parse_error = str(e)
            st.error(f"❌ JSON parsing error: {parse_error}")
    
    # Review strategy
    if review_clicked and parsed_strategy:
        st.markdown("---")
        st.header("📋 Review Results")
        
        with st.spinner("Reviewing strategy..."):
            review_result = validate_strategy(parsed_strategy)
        
        render_review_result(review_result)
        
        # Save artifact
        if review_result["verdict"] in ["approve", "revise"]:
            try:
                artifact_path = save_review_artifact(parsed_strategy, review_result)
                st.success(f"✅ Review artifact saved: `{artifact_path}`")
                
                # Show artifact content
                with st.expander("View Saved Artifact", expanded=False):
                    with open(artifact_path, "r", encoding="utf-8") as f:
                        artifact_content = json.load(f)
                        st.json(artifact_content)
            except Exception as e:
                st.error(f"❌ Failed to save artifact: {e}")
        
        # Next steps
        st.markdown("---")
        st.subheader("Next Steps")
        
        if review_result["verdict"] == "approve":
            st.success("""
            ✅ **Strategy Approved**
            
            Next steps:
            1. Strategy review artifact has been saved
            2. In production, this would trigger governance approval workflow
            3. After governance approval, strategy can be deployed to execution engine
            
            *Note: Automatic deployment is not yet implemented (TODO: Round 4.1)*
            """)
        elif review_result["verdict"] == "revise":
            st.warning("""
            ⚠️ **Strategy Needs Revision**
            
            Please address the issues listed above and re-submit for review.
            """)
        else:
            st.error("""
            ❌ **Strategy Rejected**
            
            This strategy contains prohibited fields or operations and cannot be deployed.
            """)
    
    # Previously reviewed strategies
    st.markdown("---")
    st.header("📜 Review History")
    
    review_dir = "artifacts/strategy_reviews"
    
    if os.path.exists(review_dir):
        review_files = [f for f in os.listdir(review_dir) if f.endswith(".json")]
        
        if review_files:
            st.text(f"Total reviews: {len(review_files)}")
            
            # Show recent reviews
            review_files_sorted = sorted(
                review_files,
                key=lambda f: os.path.getmtime(os.path.join(review_dir, f)),
                reverse=True
            )
            
            with st.expander(f"Show Recent Reviews ({min(10, len(review_files))})", expanded=False):
                for review_file in review_files_sorted[:10]:
                    try:
                        with open(os.path.join(review_dir, review_file), "r", encoding="utf-8") as f:
                            review_data = json.load(f)
                            strategy_id = review_data.get("strategy_id", "unknown")
                            verdict = review_data.get("review_result", {}).get("verdict", "unknown")
                            reviewed_at = review_data.get("reviewed_at", "N/A")
                            
                            st.text(f"• {strategy_id} - {verdict} ({reviewed_at})")
                    except Exception:
                        pass
        else:
            st.info("No previous reviews found")
    else:
        st.info("Review directory does not exist yet")

