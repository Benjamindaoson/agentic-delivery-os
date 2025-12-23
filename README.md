# Agentic Delivery OS - L5 Complete System

> **Long-Horizon, Self-Evolving, Governed Agent System**

A complete multi-agent AI delivery platform with long-term learning, policy evolution, and human-facing interfaces.

## 🚀 Quick Start

### One-Command Launch

```bash
# Start Web UI (default)
python run.py

# Or choose specific mode:
python run.py web    # Streamlit workbench at http://localhost:8501
python run.py api    # REST API at http://localhost:8000
python run.py cli    # Command-line interface
```

### Prerequisites

- Python 3.10+
- 2GB RAM minimum
- SQLite (bundled)

### Installation

```bash
# Clone and setup
git clone <repo>
cd agentic_delivery_os

# Install dependencies
pip install -r requirements.txt

# Run
python run.py web
```

## 🎯 System Architecture

### 10-Layer Stack

| Layer | Purpose | Artifacts |
|-------|---------|-----------|
| **1. Ingress** | Task classification, session management | `session/*.json`, `task_type/*.json` |
| **2. Planning** | Goal → Plan → DAG decomposition | `goals/*_{goal,plan,decomposition,graph}.json` |
| **3. Agents** | Long-term profiles, policy versioning | `agent_profiles/*.json`, `agent_policies/*.json` |
| **4. Tooling** | Tool stats, ROI tracking, sandbox policies | `tool_profiles/*.json`, `tool_failures/*.json` |
| **5. Memory** | Short-term traces, long-term DB, global state | `memory/long_term/`, `memory/global_state.json` |
| **6. Retrieval** | Policy-driven document retrieval | `retrieval/*.json` |
| **7. Evaluation** | Benchmark suite, regression detection | `eval/*.json`, `benchmarks/` |
| **8. Learning** | Cross-run reward, policy promotion | `learning/promotions_*.json` |
| **9. Governance** | Access control, injection guards, cost limits | (inline checks) |
| **10. Observability** | Web UI, REST API, CLI | `artifacts/**/*.json` |

## 🖥️ CLI Usage

```bash
# Execute a task
python agentctl.py run "What is machine learning?"

# Inspect a completed run
python agentctl.py inspect run_abc123

# Replay historical execution
python agentctl.py replay run_abc123

# List entities
python agentctl.py list runs
python agentctl.py list agents
python agentctl.py list tools
python agentctl.py list sessions

# Start API server
python agentctl.py serve --port 8000
```

## 🌐 REST API

Start the API server:

```bash
python run.py api
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/run` | POST | Execute a new task |
| `/session/{id}` | GET | Get session details |
| `/run/{id}` | GET | Get run details with artifacts |
| `/artifacts/{id}` | GET | Get all artifacts for a run |
| `/replay/{id}` | POST | Replay a historical run |
| `/agents` | GET | List all agent profiles |
| `/tools` | GET | List all tool profiles |
| `/runs?limit=20` | GET | List recent runs |

**API Docs:** http://localhost:8000/docs

## 🎨 Web Workbench

```bash
python run.py web
```

**Features:**
- 🚀 Run Task: Execute queries with real-time feedback
- 📊 Runs: Historical run browser with quality trends
- 🤖 Agents: Agent profiles with task affinity metrics
- 🔧 Tools: Tool usage statistics and health
- 🔍 Inspect Run: Full causal chain visualization (Goal → Plan → DAG → Evidence)
- 📈 System Stats: Global metrics and tool distribution

## 📁 Configuration

### Agent Registry

Edit `config/agents.yaml`:

```yaml
agents:
  - id: data_agent
    role: Data Specialist
    capabilities: [data_retrieval, analysis]
    allowed_tools: [retriever, summarizer]
    constraints:
      max_cost_per_run: 0.5
      max_latency_ms: 5000
```

### Tool Registry

Edit `config/tools.yaml`:

```yaml
tools:
  - id: retriever
    name: Document Retriever
    sandbox_required: false
    risk_tier: low
    permissions:
      network_access: false
      file_write: false
```

## 🔄 Artifact Structure

All decisions are stored as JSON artifacts:

```
artifacts/
├── session/          # Cross-run session state
├── task_type/        # Task classification results
├── goals/            # Goal interpretation, plans, DAGs, constraints
├── agent_profiles/   # Long-term agent performance
├── tool_profiles/    # Tool ROI and failure stats
├── eval/             # Quality scores and benchmarks
└── learning/         # Policy promotion traces
```

## ✅ Verification

Run the built-in benchmark:

```bash
python scripts/l5_benchmark.py
```

Expected output:
- ✅ All tasks complete
- ✅ Agent profiles updated
- ✅ System stats visible
- ✅ Artifacts generated

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific layer tests
pytest tests/test_l5_full_integration.py -v
```

## 🔐 Governance

### Prompt Injection Guard

Automatic detection of:
- "ignore previous instructions"
- "system prompt:"
- "you are now a"

### Cost Guardrails

Set per-session limits in `runtime/governance/l5_governance.py`:

```python
GovernanceController(cost_limit=100.0)
```

### Access Control

Agents can only use tools in their `allowed_tools` list (defined in `config/agents.yaml`).

## 📊 Long-Term Learning

The system evolves policies based on:
1. **Agent Task Affinity**: Tracks which agents excel at which task types
2. **Tool ROI**: Cost vs. value contributed
3. **Cross-Run Patterns**: SQLite-backed memory of successful/failed patterns
4. **Auto-Promotion**: Policies with quality score > 0.9 are automatically promoted

## 🛠️ Development

### Add a New Agent

1. Define in `config/agents.yaml`
2. Reload registry: `python -c "from runtime.registry.config_loader import ConfigRegistry; ConfigRegistry().export_json()"`
3. Agent is now available

### Add a New Tool

1. Define in `config/tools.yaml`
2. Implement tool logic in `runtime/tooling/`
3. Register via `ToolManager.record_usage()`

## 📈 Monitoring

View real-time system health:

```bash
# CLI
python agentctl.py list agents

# Web UI
python run.py web  # Navigate to "System Stats"

# API
curl http://localhost:8000/runs
```

## 🔗 Integration

### Python SDK

```python
from runtime.l5_engine import L5Engine

engine = L5Engine()
result = engine.execute_run("What is AI?", session_id="my_session")

print(f"Quality: {result['eval'].quality_score}")
print(f"Cost: ${result['eval'].cost}")
```

### REST API Client

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?", "user_id": "alice"}'
```

## 🎓 Acceptance Criteria

✅ **User-Facing Interfaces**: CLI, REST API, Web UI  
✅ **Full Causal Chain**: Goal → Plan → DAG → Agent → Tool → Evidence  
✅ **Replayability**: Any run can be inspected and replayed  
✅ **Long-Term Learning**: Agent/tool profiles evolve over time  
✅ **Governance**: Injection guards, cost limits, access control  
✅ **Artifact Completeness**: All decisions recorded in JSON  
✅ **One-Command Start**: `python run.py`  

## 📝 License

[Your License Here]

## 🤝 Contributing

Contributions welcome! The system is designed for extensibility:
- New agents: Add to `config/agents.yaml`
- New tools: Add to `config/tools.yaml`
- New UI pages: Extend `workbench_ui.py`
- New API endpoints: Extend `api_server.py`

---

**System Status:** 🟢 L5 Complete  
**Version:** L5.0  
**Last Updated:** 2025-12-22
