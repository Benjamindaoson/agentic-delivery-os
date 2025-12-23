"""
Diff View: Compare two tasks side-by-side
"""
import streamlit as st
from runtime.cognitive_ui.data_source import ArtifactDataSource
from runtime.cognitive_ui.components import (
    render_task_selector,
    render_diff_comparison
)


def render_diff_view(data_source: ArtifactDataSource):
    """
    Render the Diff view page
    
    Features:
    - Select two tasks to compare
    - View cost differences
    - View decision differences
    - View artifact differences
    """
    st.title("🔍 Task Diff")
    st.markdown("Compare two task executions to understand differences in cost, decisions, and artifacts.")
    
    # Task selectors
    task_ids = data_source.list_tasks()
    
    if len(task_ids) < 2:
        st.warning("⚠️ Need at least 2 tasks to perform diff comparison")
        st.info(f"Currently have {len(task_ids)} task(s) in artifacts")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Task A (Baseline)")
        task_a = render_task_selector(task_ids, key="diff_task_a")
    
    with col2:
        st.subheader("Task B (Comparison)")
        task_b = render_task_selector(task_ids, key="diff_task_b")
    
    if not task_a or not task_b:
        st.info("👆 Select both tasks to start comparison")
        return
    
    if task_a == task_b:
        st.warning("⚠️ Selected tasks are the same. Please choose different tasks to compare.")
        return
    
    # Compute diff
    st.markdown("---")
    
    with st.spinner("Computing differences..."):
        diff = data_source.diff_tasks(task_a, task_b)
    
    # Render diff comparison
    render_diff_comparison(diff)
    
    # Detailed comparison sections
    st.markdown("---")
    
    # Cost breakdown detail
    with st.expander("📊 Detailed Cost Breakdown", expanded=True):
        cost_diff = diff.get("cost_diff", {})
        breakdown_a = cost_diff.get("breakdown_a", {})
        breakdown_b = cost_diff.get("breakdown_b", {})
        
        # Combine all providers
        all_providers = set(breakdown_a.keys()) | set(breakdown_b.keys())
        
        if all_providers:
            st.subheader("Cost by Provider")
            
            for provider in sorted(all_providers):
                cost_a = breakdown_a.get(provider, 0.0)
                cost_b = breakdown_b.get(provider, 0.0)
                delta = cost_b - cost_a
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.text(f"{provider}:")
                with col2:
                    st.text(f"A: ${cost_a:.4f} | B: ${cost_b:.4f}")
                with col3:
                    if delta > 0:
                        st.text(f"Δ +${delta:.4f} ⬆️")
                    elif delta < 0:
                        st.text(f"Δ ${delta:.4f} ⬇️")
                    else:
                        st.text(f"Δ ${delta:.4f} ➡️")
        else:
            st.info("No cost breakdown available")
    
    # Decision comparison detail
    with st.expander("⚖️ Detailed Decision Comparison", expanded=False):
        decision_diff = diff.get("decision_diff", {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Task A")
            st.text(f"Degraded: {decision_diff.get('degraded_a', False)}")
            st.text(f"Decision Count: {decision_diff.get('decisions_count_a', 0)}")
        
        with col2:
            st.subheader("Task B")
            st.text(f"Degraded: {decision_diff.get('degraded_b', False)}")
            st.text(f"Decision Count: {decision_diff.get('decisions_count_b', 0)}")
    
    # Artifact list detail
    with st.expander("📁 Detailed Artifact List", expanded=False):
        artifact_diff = diff.get("artifact_diff", {})
        
        only_a = artifact_diff.get("only_in_a", [])
        only_b = artifact_diff.get("only_in_b", [])
        in_both = artifact_diff.get("in_both", [])
        
        st.subheader(f"Only in Task A ({len(only_a)})")
        if only_a:
            for item in only_a:
                st.text(f"  ❌ {item}")
        else:
            st.text("  (none)")
        
        st.subheader(f"Only in Task B ({len(only_b)})")
        if only_b:
            for item in only_b:
                st.text(f"  ➕ {item}")
        else:
            st.text("  (none)")
        
        st.subheader(f"In Both ({len(in_both)})")
        if in_both:
            for item in in_both:
                st.text(f"  ✅ {item}")
        else:
            st.text("  (none)")
    
    # Export diff
    st.markdown("---")
    st.header("📦 Export Diff")
    
    if st.button("📥 Download Diff JSON"):
        import json
        json_str = json.dumps(diff, indent=2)
        st.download_button(
            label="Download",
            data=json_str,
            file_name=f"diff_{task_a}_vs_{task_b}.json",
            mime="application/json"
        )

