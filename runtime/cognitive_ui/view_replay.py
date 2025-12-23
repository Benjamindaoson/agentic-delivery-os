"""
Replay View: Task execution replay and timeline visualization
"""
import streamlit as st
from typing import Optional
from runtime.cognitive_ui.data_source import ArtifactDataSource
from runtime.cognitive_ui.components import (
    render_task_selector,
    render_info_card,
    render_timeline_table,
    render_cost_breakdown,
    render_governance_summary
)


def render_replay_view(data_source: ArtifactDataSource):
    """
    Render the Replay view page
    
    Features:
    - Select a task
    - View task summary
    - View timeline events
    - View cost summary
    - View governance summary
    """
    st.title("🎬 Task Replay")
    st.markdown("View detailed execution traces and timeline for any completed task.")
    
    # Task selector
    task_ids = data_source.list_tasks()
    selected_task = render_task_selector(task_ids, key="replay_task_selector")
    
    if not selected_task:
        st.info("👈 Select a task from the dropdown to view its replay")
        
        # Show available tasks
        if task_ids:
            st.subheader("Available Tasks")
            st.text(f"Total tasks: {len(task_ids)}")
            with st.expander("Show all task IDs", expanded=False):
                for task_id in task_ids:
                    st.text(f"  - {task_id}")
        return
    
    # Load task data
    with st.spinner(f"Loading data for {selected_task}..."):
        summary = data_source.load_task_summary(selected_task)
        timeline_events = data_source.load_timeline_events(selected_task)
        cost_info = data_source.load_cost(selected_task)
        governance_info = data_source.load_governance(selected_task)
        plan_info = data_source.load_plan_or_dag(selected_task)
    
    # Task Summary Card
    st.header("📋 Task Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status = summary.get("status", "unknown")
        if status == "completed":
            st.success(f"Status: {status.upper()}")
        elif status == "failed":
            st.error(f"Status: {status.upper()}")
        else:
            st.info(f"Status: {status.upper()}")
    
    with col2:
        st.metric("Agents Executed", len(summary.get("agents_executed", [])))
    
    with col3:
        created_at = summary.get("created_at", "N/A")
        st.text(f"Created: {created_at}")
    
    # Error display (if failed)
    if summary.get("error"):
        st.error(f"❌ Error: {summary.get('error')}")
    
    # Spec details
    spec = summary.get("spec", {})
    if spec:
        render_info_card("Task Specification", spec, expandable=True)
    
    # Timeline Events
    st.header("⏱️ Timeline")
    render_timeline_table(timeline_events)
    
    # Cost Breakdown
    st.header("💰 Cost")
    render_cost_breakdown(cost_info)
    
    # Governance Summary
    st.header("⚖️ Governance")
    render_governance_summary(governance_info)
    
    # Execution Plan/DAG (if available)
    if plan_info:
        st.header("📊 Execution Plan")
        with st.expander("View Execution Plan Details", expanded=False):
            st.json(plan_info)
    
    # Raw Data Export
    st.header("📦 Export")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Download Summary JSON", key="download_summary"):
            import json
            json_str = json.dumps(summary, indent=2)
            st.download_button(
                label="Download",
                data=json_str,
                file_name=f"{selected_task}_summary.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📥 Download Timeline JSON", key="download_timeline"):
            import json
            json_str = json.dumps(timeline_events, indent=2)
            st.download_button(
                label="Download",
                data=json_str,
                file_name=f"{selected_task}_timeline.json",
                mime="application/json"
            )

