"""
Cognitive Workbench - Main Streamlit App
Entry point for the UI workbench
"""
import streamlit as st
import os
from runtime.cognitive_ui.data_source import ArtifactDataSource
from runtime.cognitive_ui.view_replay import render_replay_view
from runtime.cognitive_ui.view_diff import render_diff_view
from runtime.cognitive_ui.view_strategy_lab import render_strategy_lab_view


# Page config
st.set_page_config(
    page_title="Cognitive Workbench",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main():
    """Main app entry point"""
    
    # Sidebar
    with st.sidebar:
        st.title("🧠 Cognitive Workbench")
        st.markdown("**Agentic AI Delivery OS**")
        st.markdown("---")
        
        # Page selector
        page = st.radio(
            "Navigate",
            options=["🎬 Replay", "🔍 Diff", "🧪 Strategy Lab"],
            index=0
        )
        
        st.markdown("---")
        
        # Data source config
        st.subheader("⚙️ Configuration")
        
        artifacts_root = st.text_input(
            "Artifacts Directory",
            value="./artifacts",
            help="Root directory for artifacts (relative or absolute path)"
        )
        
        # Initialize data source
        if "data_source" not in st.session_state or st.session_state.get("artifacts_root") != artifacts_root:
            try:
                st.session_state.data_source = ArtifactDataSource(artifacts_root)
                st.session_state.artifacts_root = artifacts_root
                
                # Check if directory exists
                if os.path.exists(artifacts_root):
                    st.success("✅ Connected")
                    
                    # Show stats
                    task_count = len(st.session_state.data_source.list_tasks())
                    st.metric("Available Tasks", task_count)
                else:
                    st.error("❌ Directory not found")
            except Exception as e:
                st.error(f"❌ Error: {e}")
        
        st.markdown("---")
        
        # Info
        with st.expander("ℹ️ About", expanded=False):
            st.markdown("""
            **Cognitive Workbench** is the observability and strategy design interface for Agentic AI Delivery OS.
            
            **Features:**
            - 🎬 **Replay**: View task execution traces and timelines
            - 🔍 **Diff**: Compare two tasks side-by-side
            - 🧪 **Strategy Lab**: Design and review custom strategies
            
            **Version:** Round 4 MVP (UI-First)
            """)
        
        # Quick actions
        st.markdown("---")
        st.subheader("🚀 Quick Actions")
        
        if st.button("🔄 Refresh Data"):
            if "data_source" in st.session_state:
                st.session_state.data_source = ArtifactDataSource(st.session_state.artifacts_root)
                st.success("Data refreshed!")
                st.experimental_rerun()
    
    # Main content area
    data_source = st.session_state.get("data_source")
    
    if not data_source:
        st.error("⚠️ Data source not initialized. Please check the artifacts directory in the sidebar.")
        return
    
    # Route to selected page
    if page == "🎬 Replay":
        render_replay_view(data_source)
    elif page == "🔍 Diff":
        render_diff_view(data_source)
    elif page == "🧪 Strategy Lab":
        render_strategy_lab_view()
    else:
        st.error(f"Unknown page: {page}")


if __name__ == "__main__":
    main()

