import streamlit as st
import json
import os
import sys
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from runtime.l5_engine import L5Engine

st.set_page_config(page_title="Agentic OS", layout="wide", page_icon="🤖")

# Initialize engine
@st.cache_resource
def get_engine():
    return L5Engine()

engine = get_engine()

# Sidebar navigation
st.sidebar.title("🤖 Agentic OS L5")
page = st.sidebar.radio("Navigate", ["🚀 Run Task", "📊 Runs", "🤖 Agents", "🔧 Tools", "🔍 Inspect Run", "📈 System Stats"])

# Page 1: Run Task
if page == "🚀 Run Task":
    st.title("🚀 Execute New Task")
    
    query = st.text_area("Enter your query:", height=100, placeholder="What is machine learning?")
    col1, col2 = st.columns(2)
    with col1:
        session_id = st.text_input("Session ID (optional):", "")
    with col2:
        user_id = st.text_input("User ID:", "default_user")
    
    if st.button("▶️ Execute", type="primary"):
        if query:
            with st.spinner("Executing..."):
                result = engine.execute_run(query, session_id if session_id else None, user_id)
                
                st.success(f"✅ Run completed: {result['run_id']}")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Quality", f"{result['eval'].quality_score:.1%}")
                col2.metric("Cost", f"${result['eval'].cost:.4f}")
                col3.metric("Latency", f"{result['eval'].latency:.0f}ms")
                col4.metric("Status", "✅" if result['eval'].success else "❌")
                
                with st.expander("📋 Plan Details"):
                    plan = result['plan']['plan']
                    st.write(f"**Strategy:** {plan.strategy_selected}")
                    st.write(f"**Stages:** {' → '.join(plan.stages)}")
                
                with st.expander("🎯 Goal Interpretation"):
                    goal = result['plan']['goal']
                    st.write(f"**Primary Goal:** {goal.primary_goal}")
                    st.write(f"**Success Criteria:** {', '.join(goal.success_criteria)}")
                    st.write(f"**Confidence:** {goal.confidence_score:.1%}")

# Page 2: Runs List
elif page == "📊 Runs":
    st.title("📊 Run History")
    
    eval_dir = "artifacts/eval"
    if os.path.exists(eval_dir):
        runs = []
        for file in sorted(os.listdir(eval_dir), key=lambda x: os.path.getmtime(f"{eval_dir}/{x}"), reverse=True)[:50]:
            with open(f"{eval_dir}/{file}") as f:
                data = json.load(f)
                runs.append({
                    "Run ID": data['run_id'],
                    "Task Type": data['task_type'],
                    "Quality": data['quality_score'],
                    "Cost": data['cost'],
                    "Latency (ms)": data['latency'],
                    "Success": "✅" if data['success'] else "❌",
                    "Timestamp": data.get('timestamp', 'N/A')
                })
        
        df = pd.DataFrame(runs)
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Runs", len(runs))
        col2.metric("Avg Quality", f"{df['Quality'].mean():.1%}")
        col3.metric("Success Rate", f"{(df['Success'] == '✅').sum() / len(runs):.1%}")
        
        # Chart
        fig = px.line(df, y='Quality', title='Quality Score Trend')
        st.plotly_chart(fig, use_container_width=True)
        
        # Table
        st.dataframe(df, use_container_width=True, hide_index=True)

# Page 3: Agents
elif page == "🤖 Agents":
    st.title("🤖 Agent Profiles")
    
    agents_dir = "artifacts/agent_profiles"
    if os.path.exists(agents_dir):
        for file in os.listdir(agents_dir):
            with open(f"{agents_dir}/{file}") as f:
                agent = json.load(f)
                
                with st.expander(f"**{agent['agent_id']}** {'✅' if agent.get('is_enabled', True) else '❌'}"):
                    col1, col2, col3 = st.columns(3)
                    
                    perf = agent.get('performance', {})
                    col1.metric("Success Rate", f"{perf.get('success_rate', agent.get('success_rate', 0)):.1%}")
                    col2.metric("Avg Latency", f"{perf.get('avg_latency', agent.get('avg_latency_ms', 0)):.0f}ms")
                    col3.metric("Total Runs", perf.get('total_runs', agent.get('total_runs', 0)))
                    
                    if perf.get('task_type_affinity') or agent.get('task_affinities'):
                        st.write("**Task Affinities:**")
                        affinity_data = perf.get('task_type_affinity', agent.get('task_affinities', {}))
                        if affinity_data:
                            st.json(affinity_data)

# Page 4: Tools
elif page == "🔧 Tools":
    st.title("🔧 Tool Profiles")
    
    tools_dir = "artifacts/tool_profiles"
    if os.path.exists(tools_dir):
        tools_data = []
        for file in os.listdir(tools_dir):
            with open(f"{tools_dir}/{file}") as f:
                tool = json.load(f)
                stats = tool.get('stats', {})
                tools_data.append({
                    "Tool": tool['tool_id'],
                    "Status": "✅" if tool.get('is_enabled', tool.get('enabled', True)) else "❌",
                    "Uses": stats.get('total_uses', tool.get('total_invocations', 0)),
                    "Success Rate": f"{tool.get('success_rate', 0):.1%}",
                    "Avg Latency": f"{tool.get('avg_latency_ms', stats.get('avg_latency', 0)):.0f}ms"
                })
        
        df = pd.DataFrame(tools_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

# Page 5: Inspect Run
elif page == "🔍 Inspect Run":
    st.title("🔍 Inspect Run")
    
    run_id = st.text_input("Enter Run ID:")
    
    if st.button("🔎 Inspect"):
        goal_path = f"artifacts/goals/{run_id}_goal_interpretation.json"
        if os.path.exists(goal_path):
            # Load all artifacts
            with open(goal_path) as f:
                goal = json.load(f)
            
            plan_path = f"artifacts/goals/{run_id}_high_level_plan.json"
            with open(plan_path) as f:
                plan = json.load(f)
            
            decomp_path = f"artifacts/goals/{run_id}_task_decomposition.json"
            with open(decomp_path) as f:
                decomp = json.load(f)
            
            eval_path = f"artifacts/eval/{run_id}.json"
            with open(eval_path) as f:
                eval_data = json.load(f)
            
            # Display
            st.subheader("🎯 Goal")
            st.write(f"**Primary Goal:** {goal['primary_goal']}")
            st.write(f"**Confidence:** {goal['confidence_score']:.1%}")
            
            st.subheader("📋 Plan")
            st.write(f"**Strategy:** {plan['strategy_selected']}")
            st.write(f"**Stages:** {' → '.join(plan['stages'])}")
            
            st.subheader("📊 Execution DAG")
            # Create DAG visualization
            steps = decomp['steps']
            fig = go.Figure()
            for i, step in enumerate(steps):
                fig.add_trace(go.Scatter(
                    x=[i], y=[0],
                    mode='markers+text',
                    text=[step['title']],
                    textposition="top center",
                    marker=dict(size=20, color='lightblue')
                ))
            
            fig.update_layout(
                title="Task Decomposition",
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=200
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("📈 Evaluation")
            col1, col2, col3 = st.columns(3)
            col1.metric("Quality", f"{eval_data['quality_score']:.1%}")
            col2.metric("Cost", f"${eval_data['cost']:.4f}")
            col3.metric("Latency", f"{eval_data['latency']:.0f}ms")
        else:
            st.error("Run not found")

# Page 6: System Stats
elif page == "📈 System Stats":
    st.title("📈 System Statistics")
    
    # Load global state
    state_path = "memory/global_state.json"
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
            metrics = state.get('metrics', state)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Runs", metrics.get('total_runs', 0))
            col2.metric("Success Rate", f"{metrics.get('avg_success_rate', 0):.1%}")
            col3.metric("Cumulative Cost", f"${metrics.get('total_cost', 0):.4f}")
            col4.metric("System Version", state.get('system_version', 'L5.0'))
            
            if 'tool_usage_stats' in state:
                st.subheader("🔧 Tool Usage Distribution")
                tool_data = pd.DataFrame(list(state['tool_usage_stats'].items()), columns=['Tool', 'Usage'])
                fig = px.bar(tool_data, x='Tool', y='Usage', title='Tool Usage Count')
                st.plotly_chart(fig, use_container_width=True)



