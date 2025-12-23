"""
Common UI components for Cognitive Workbench
Reusable Streamlit components
"""
import streamlit as st
from typing import List, Dict, Any, Optional
import json


def render_task_selector(task_ids: List[str], key: str = "task_selector") -> Optional[str]:
    """
    Render a task selector dropdown
    
    Args:
        task_ids: List of task IDs
        key: Unique key for the widget
        
    Returns:
        Selected task_id or None
    """
    if not task_ids:
        st.warning("No tasks found in artifacts directory")
        return None
    
    selected = st.selectbox(
        "Select Task ID",
        options=[""] + task_ids,
        key=key,
        help="Choose a task to view details"
    )
    
    return selected if selected else None


def render_info_card(title: str, data: Dict[str, Any], expandable: bool = False):
    """
    Render an info card with key-value pairs
    
    Args:
        title: Card title
        data: Dictionary of key-value pairs
        expandable: If True, render in an expander
    """
    def render_content():
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                st.text(f"{key}:")
                st.json(value)
            else:
                st.text(f"{key}: {value}")
    
    if expandable:
        with st.expander(title, expanded=False):
            render_content()
    else:
        st.subheader(title)
        render_content()


def render_timeline_table(events: List[Dict[str, Any]]):
    """
    Render timeline events as an expandable table
    
    Args:
        events: List of timeline events
    """
    if not events:
        st.info("No timeline events available")
        return
    
    st.subheader(f"Timeline Events ({len(events)} events)")
    
    for i, event in enumerate(events):
        timestamp = event.get("timestamp", "N/A")
        event_type = event.get("type", "unknown")
        status = event.get("status", "N/A")
        
        # Summary line
        summary = f"**[{timestamp}]** {event_type}"
        if event_type == "agent_execution":
            summary += f" - {event.get('agent', 'N/A')} ({status})"
        elif event_type == "governance_decision":
            summary += f" - {event.get('execution_mode', 'N/A')}"
        elif event_type == "tool_execution":
            summary += f" - {event.get('tool_name', 'N/A')} ({status})"
        
        with st.expander(summary, expanded=False):
            st.json(event.get("details", {}))


def render_cost_breakdown(cost_info: Dict[str, Any]):
    """
    Render cost breakdown visualization
    
    Args:
        cost_info: Cost information dictionary
    """
    st.subheader("Cost Breakdown")
    
    total_cost = cost_info.get("total_cost", 0.0)
    breakdown = cost_info.get("cost_breakdown", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Cost", f"${total_cost:.4f}")
    
    with col2:
        if breakdown:
            st.text("Breakdown by Provider:")
            for provider, cost in breakdown.items():
                st.text(f"  {provider}: ${cost:.4f}")
        else:
            st.text("No breakdown available")
    
    # Cost decision (if available)
    cost_decision = cost_info.get("cost_decision")
    if cost_decision:
        with st.expander("Cost Decision Details", expanded=False):
            st.json(cost_decision)


def render_governance_summary(governance_info: Dict[str, Any]):
    """
    Render governance summary
    
    Args:
        governance_info: Governance information dictionary
    """
    st.subheader("Governance Summary")
    
    decisions = governance_info.get("decisions", [])
    degraded = governance_info.get("degraded", False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Governance Decisions", len(decisions))
    
    with col2:
        if degraded:
            st.error("⚠️ Degraded Mode Detected")
        else:
            st.success("✅ Normal Execution")
    
    if decisions:
        with st.expander(f"View All Decisions ({len(decisions)})", expanded=False):
            for i, decision in enumerate(decisions):
                st.text(f"Decision {i+1}:")
                st.json(decision)


def render_diff_comparison(diff: Dict[str, Any]):
    """
    Render side-by-side diff comparison
    
    Args:
        diff: Diff dictionary from ArtifactDataSource.diff_tasks
    """
    task_a = diff.get("task_a", "")
    task_b = diff.get("task_b", "")
    
    st.header(f"Diff: {task_a} vs {task_b}")
    
    # Cost diff
    st.subheader("💰 Cost Comparison")
    cost_diff = diff.get("cost_diff", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Task A Cost", f"${cost_diff.get('total_cost_a', 0.0):.4f}")
    
    with col2:
        st.metric("Task B Cost", f"${cost_diff.get('total_cost_b', 0.0):.4f}")
    
    with col3:
        delta = cost_diff.get('delta', 0.0)
        st.metric("Delta", f"${delta:.4f}", delta=f"{delta:.4f}")
    
    # Decision diff
    st.subheader("⚖️ Decision Comparison")
    decision_diff = diff.get("decision_diff", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.text(f"Task A: {'Degraded' if decision_diff.get('degraded_a') else 'Normal'}")
        st.text(f"Decisions: {decision_diff.get('decisions_count_a', 0)}")
    
    with col2:
        st.text(f"Task B: {'Degraded' if decision_diff.get('degraded_b') else 'Normal'}")
        st.text(f"Decisions: {decision_diff.get('decisions_count_b', 0)}")
    
    # Artifact diff
    st.subheader("📁 Artifact Comparison")
    artifact_diff = diff.get("artifact_diff", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.text("Only in Task A:")
        only_a = artifact_diff.get("only_in_a", [])
        if only_a:
            for item in only_a:
                st.text(f"  - {item}")
        else:
            st.text("  (none)")
    
    with col2:
        st.text("Only in Task B:")
        only_b = artifact_diff.get("only_in_b", [])
        if only_b:
            for item in only_b:
                st.text(f"  - {item}")
        else:
            st.text("  (none)")
    
    with col3:
        st.text("In Both:")
        in_both = artifact_diff.get("in_both", [])
        if in_both:
            st.text(f"  {len(in_both)} files")
        else:
            st.text("  (none)")


def render_json_editor(label: str, initial_value: Dict[str, Any], key: str) -> str:
    """
    Render a JSON/YAML text editor
    
    Args:
        label: Label for the text area
        initial_value: Initial JSON value
        key: Unique key for the widget
        
    Returns:
        Edited text content
    """
    initial_text = json.dumps(initial_value, indent=2)
    
    edited_text = st.text_area(
        label,
        value=initial_text,
        height=300,
        key=key,
        help="Edit JSON content (must be valid JSON)"
    )
    
    return edited_text


def render_review_result(review_result: Dict[str, Any]):
    """
    Render strategy review result
    
    Args:
        review_result: Review result dictionary
    """
    verdict = review_result.get("verdict", "unknown")
    reason = review_result.get("reason", "")
    issues = review_result.get("issues", [])
    
    st.subheader("Review Result")
    
    if verdict == "approve":
        st.success(f"✅ Approved: {reason}")
    elif verdict == "revise":
        st.warning(f"⚠️ Needs Revision: {reason}")
    elif verdict == "reject":
        st.error(f"❌ Rejected: {reason}")
    else:
        st.info(f"ℹ️ {verdict}: {reason}")
    
    if issues:
        st.subheader("Issues Found")
        for i, issue in enumerate(issues):
            st.text(f"{i+1}. {issue}")

