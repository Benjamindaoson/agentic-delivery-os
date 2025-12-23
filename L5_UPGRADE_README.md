# Agentic Delivery OS - L5 Full Body

This upgrade transforms the system into an **L5 (Long-Horizon, Self-Evolving, Governed Agent System)**.

## 🚀 Key Features

- **Long-term Session Management**: Supports cross-run/day user sessions with dedicated memory and policy.
- **Explicit Goal-to-Outcome Chain**: Produces a full causal chain of artifacts for every run.
- **Agent & Tool Lifecycle Governance**: Long-term profiles, task affinities, auto-degradation, and policy versioning.
- **Three-Layer Memory**: Short-term traces, Long-term hybrid memory (SQLite/Vector), and Global State Store.
- **Active Governance**: Prompt injection guards, cost guardrails, and access control decisions.
- **Workbench Inspection**: Minimal CLI for viewing system trends and agent profiles.

## 📁 Artifacts Structure

- `artifacts/session/`: Session state and history.
- `artifacts/task_type/`: Task classification results.
- `artifacts/goals/`: Full causal chain (Goal, Plan, Decomposition, Graph, Constraints, Rationale).
- `artifacts/agent_profiles/`: Long-term agent performance and affinity.
- `artifacts/tool_profiles/`: Tool stats and ROI scores.
- `artifacts/tool_failures/`: Replayable tool failure traces.
- `artifacts/eval/`: Benchmark and regression results.
- `artifacts/learning/`: Policy promotion traces.
- `memory/long_term/`: Structured and vector memory.
- `memory/global_state.json`: Cross-session system metrics.

## 🛠️ How to Execute

### 1. Run L5 Benchmark
Execute the standardized benchmark tasks to verify the full body system:
```bash
python scripts/l5_benchmark.py
```

### 2. View Agent Profiles
```python
from runtime.workbench.cli import WorkbenchCLI
cli = WorkbenchCLI()
cli.show_agent_profiles()
```

### 3. Check Global Trends
```python
cli.show_system_trends()
```

## ✅ Acceptance Criteria Status

- **100% Replayable**: All decisions stored in JSON artifacts.
- **Long-term Profiles**: Implemented for Agent, Tool, and Planner behavior.
- **Self-Evolution**: Learning controller promotes successful policies based on quality gain.
- **Governance**: Injection guards and cost guardrails active.



