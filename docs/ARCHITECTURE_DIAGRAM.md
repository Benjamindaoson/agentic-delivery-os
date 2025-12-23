# System Architecture Diagram

> Version: 2.0.0 (Industrial Upgrade)
> Generated: 2025-12-22

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AGENTIC AI DELIVERY OS                                │
│                         (Industrial-Grade v2.0.0)                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           INGRESS LAYER                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                      │   │
│  │  │    CLI      │  │  REST API   │  │  Workbench  │                      │   │
│  │  │  agentctl   │  │   /delivery │  │  Streamlit  │                      │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                      │   │
│  │         └─────────────────┴─────────────────┘                            │   │
│  │                           │                                              │   │
│  │                    ┌──────▼──────┐                                       │   │
│  │                    │  Classifier │                                       │   │
│  │                    │ + Session   │                                       │   │
│  │                    └─────────────┘                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                          PLANNING LAYER (P0-1 Upgrade)                   │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                    LLM Planner                                   │    │   │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │    │   │
│  │  │  │ Complexity │  │  Template  │  │    Goal    │  │  Replan   │ │    │   │
│  │  │  │ Assessment │→ │  Selection │→ │ Decompose  │→ │ on Fail   │ │    │   │
│  │  │  └────────────┘  └────────────┘  └────────────┘  └───────────┘ │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                   │                                      │   │
│  │  Artifacts: goal_decomposition.json, planning_rationale.md              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       EXECUTION LAYER (P0-2 Upgrade)                     │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                   Evolvable DAG                                  │    │   │
│  │  │                                                                  │    │   │
│  │  │    ┌─────────┐     ┌─────────┐     ┌─────────┐                 │    │   │
│  │  │    │ Product │ ──▶ │  Data   │ ──▶ │ Execute │ ──▶ ...        │    │   │
│  │  │    └─────────┘     └─────────┘     └─────────┘                 │    │   │
│  │  │         │               │               │                       │    │   │
│  │  │         ▼               ▼               ▼                       │    │   │
│  │  │    [inject]         [skip]          [merge]                     │    │   │
│  │  │                                                                  │    │   │
│  │  │    ┌──────────────────────────────────────────────┐            │    │   │
│  │  │    │  Mutation History │ Snapshots │ Rollback     │            │    │   │
│  │  │    └──────────────────────────────────────────────┘            │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  Artifacts: dag_evolution.json, snapshots                               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         AGENT LAYER (P2-1 Upgrade)                       │   │
│  │                                                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │              Protocol-Based Agents                               │    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │   │
│  │  │  │   Product    │  │     Data     │  │  Execution   │          │    │   │
│  │  │  │    Agent     │  │    Agent     │  │    Agent     │          │    │   │
│  │  │  ├──────────────┤  ├──────────────┤  ├──────────────┤          │    │   │
│  │  │  │ Input Schema │  │ Input Schema │  │ Input Schema │          │    │   │
│  │  │  │Output Schema │  │Output Schema │  │Output Schema │          │    │   │
│  │  │  │ Side Effects │  │ Side Effects │  │ Side Effects │          │    │   │
│  │  │  │   Manifest   │  │   Manifest   │  │   Manifest   │          │    │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘          │    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌──────────────┐  ┌──────────────┐                            │    │   │
│  │  │  │  Evaluation  │  │     Cost     │                            │    │   │
│  │  │  │    Agent     │  │    Agent     │                            │    │   │
│  │  │  └──────────────┘  └──────────────┘                            │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  │                                                                          │   │
│  │  Validation: AgentComplianceChecker                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      GOVERNANCE LAYER                                    │   │
│  │                                                                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │   Access   │  │  Injection │  │    Cost    │  │   Gate     │        │   │
│  │  │  Control   │  │   Guard    │  │  Guardrail │  │  Executor  │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Governance Engine (Checkpoints)                    │     │   │
│  │  │  - Conflict detection                                          │     │   │
│  │  │  - Execution mode decisions (normal/degraded/minimal/paused)   │     │   │
│  │  │  - Budget enforcement                                          │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       LEARNING LAYER (P0-3/P3 Upgrade)                   │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Unified Policy Framework                           │     │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │     │   │
│  │  │  │  Bandit  │  │ Context  │  │ Offline  │  │   Meta   │       │     │   │
│  │  │  │  (UCB1)  │  │  Bandit  │  │    RL    │  │ Learning │       │     │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │     │   │
│  │  │         │            │            │             │              │     │   │
│  │  │         └────────────┴────────────┴─────────────┘              │     │   │
│  │  │                          │                                      │     │   │
│  │  │                   PolicyMigrator                                │     │   │
│  │  │              (paradigm migration support)                       │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Structural Learning                                │     │   │
│  │  │  - DAG-level reward computation                                 │     │   │
│  │  │  - Structural credit assignment                                 │     │   │
│  │  │  - Task type → DAG structure mapping                           │     │   │
│  │  │  - Feature importance learning                                  │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Task Success Reward                                │     │   │
│  │  │  35% task_success + 25% quality + 15% satisfaction             │     │   │
│  │  │  + 15% cost_efficiency + 10% latency_efficiency                │     │   │
│  │  │  → Explainable, traceable rewards                              │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      TENANCY LAYER (P1-2 Upgrade)                        │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Tenant Learning Controller                         │     │   │
│  │  │                                                                  │     │   │
│  │  │  ┌─────────────────┐    ┌─────────────────┐                    │     │   │
│  │  │  │  Tenant-Local   │    │  Cross-Tenant   │                    │     │   │
│  │  │  │   Knowledge     │    │    Patterns     │                    │     │   │
│  │  │  │   (isolated)    │    │  (anonymized)   │                    │     │   │
│  │  │  └─────────────────┘    └─────────────────┘                    │     │   │
│  │  │                                                                  │     │   │
│  │  │  Features:                                                      │     │   │
│  │  │  - Cold-start strategies (default/clone/meta/conservative)     │     │   │
│  │  │  - Budget → Learning intensity linkage                         │     │   │
│  │  │  - Privacy-preserving pattern sharing                          │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    COGNITIVE UI LAYER (P1-1 Upgrade)                     │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              Strategy Designer                                  │     │   │
│  │  │                                                                  │     │   │
│  │  │  User Actions:                                                  │     │   │
│  │  │  - Compose strategies from components                          │     │   │
│  │  │  - Adjust weights and thresholds                               │     │   │
│  │  │  - Toggle agents on/off                                        │     │   │
│  │  │  - Submit for governance review                                │     │   │
│  │  │                                                                  │     │   │
│  │  │  Workflow: DRAFT → PENDING_REVIEW → APPROVED → ACTIVE          │     │   │
│  │  │                                                                  │     │   │
│  │  │  ┌─────────────────────────────────────────────────────┐       │     │   │
│  │  │  │  convert_to_executable_policy()                      │       │     │   │
│  │  │  │  Maps UI designs to runtime execution                │       │     │   │
│  │  │  └─────────────────────────────────────────────────────┘       │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                     OBSERVABILITY LAYER                                  │   │
│  │                                                                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │   Trace    │  │  Metrics   │  │  Artifacts │  │   Replay   │        │   │
│  │  │   Store    │  │  Registry  │  │   Storage  │  │   Engine   │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │   │
│  │                                                                          │   │
│  │  ┌────────────────────────────────────────────────────────────────┐     │   │
│  │  │              System Regression Suite (P2-2)                     │     │   │
│  │  │  - DAG stability tests                                         │     │   │
│  │  │  - Cost regression tests                                       │     │   │
│  │  │  - Latency degradation tests                                   │     │   │
│  │  │  - Learning regression tests                                   │     │   │
│  │  │  → SYSTEM_HEALTH_REPORT.json                                   │     │   │
│  │  └────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Learning Closed Loop

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        LEARNING CLOSED LOOP                                   │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│    ┌──────────────┐                                                          │
│    │   Execute    │                                                          │
│    │     Run      │                                                          │
│    └──────┬───────┘                                                          │
│           │                                                                   │
│           ▼                                                                   │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            │
│    │    State     │ ───▶ │    Action    │ ───▶ │   Outcome    │            │
│    │  Extraction  │      │  Selection   │      │  Observation │            │
│    └──────────────┘      └──────────────┘      └──────────────┘            │
│                                                        │                      │
│                                                        ▼                      │
│                                               ┌──────────────┐               │
│                                               │    Reward    │               │
│                                               │   Computer   │               │
│                                               │              │               │
│                                               │ task_success │               │
│                                               │ quality      │               │
│                                               │ satisfaction │               │
│                                               │ efficiency   │               │
│                                               └──────┬───────┘               │
│                                                      │                        │
│           ┌──────────────────────────────────────────┼────────────────┐      │
│           │                                          │                │      │
│           ▼                                          ▼                ▼      │
│    ┌──────────────┐                         ┌──────────────┐  ┌──────────┐  │
│    │  Structural  │                         │   Unified    │  │  Tenant  │  │
│    │   Learner    │                         │   Policy     │  │  Learner │  │
│    │              │                         │              │  │          │  │
│    │ - DAG credit │                         │ - Bandit     │  │ - Local  │  │
│    │ - Structure  │                         │ - Context    │  │ - Cross  │  │
│    │   rewards    │                         │ - RL         │  │          │  │
│    └──────────────┘                         └──────────────┘  └──────────┘  │
│           │                                          │                │      │
│           └──────────────────────────────────────────┼────────────────┘      │
│                                                      │                        │
│                                                      ▼                        │
│                                               ┌──────────────┐               │
│                                               │   Policy     │               │
│                                               │    Store     │               │
│                                               └──────────────┘               │
│                                                      │                        │
│                                                      ▼                        │
│                                               ┌──────────────┐               │
│                                               │   Shadow     │               │
│                                               │   Eval       │               │
│                                               └──────────────┘               │
│                                                      │                        │
│                                                      ▼                        │
│                                               ┌──────────────┐               │
│                                               │    A/B       │               │
│                                               │    Gate      │               │
│                                               └──────────────┘               │
│                                                      │                        │
│                                                      ▼                        │
│                                               ┌──────────────┐               │
│                                               │   Rollout    │               │
│                                               │   Manager    │               │
│                                               │              │               │
│                                               │ canary →     │               │
│                                               │ partial →    │               │
│                                               │ full         │               │
│                                               └──────────────┘               │
│                                                      │                        │
│                                                      ▼                        │
│                                               ┌──────────────┐               │
│                                               │   Execute    │ ◀────────────┘
│                                               │     Run      │
│                                               └──────────────┘
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
agentic_delivery_os/
├── runtime/
│   ├── planning/
│   │   ├── l5_planner.py          # Original planner
│   │   ├── llm_planner.py         # NEW: LLM-assisted planner
│   │   └── goal_interpreter.py    # Goal interpretation
│   ├── execution_graph/
│   │   ├── execution_engine.py    # Core execution engine
│   │   └── evolvable_dag.py       # NEW: Evolvable DAG
│   ├── agents/
│   │   ├── base_agent.py          # Original base class
│   │   ├── agent_protocol.py      # NEW: Protocol-based interface
│   │   ├── product_agent.py
│   │   ├── data_agent.py
│   │   ├── execution_agent.py
│   │   ├── evaluation_agent.py
│   │   └── cost_agent.py
│   ├── cognitive_ui/
│   │   ├── strategy_simulator.py  # Original simulator
│   │   └── strategy_designer.py   # NEW: Strategy composition
│   └── tenancy/
│       └── tenant.py              # Tenant management
├── learning/
│   ├── bandit_selector.py         # Original bandit
│   ├── offline_rl.py              # Original RL
│   ├── meta_policy.py             # Original meta-learning
│   ├── structural_learning.py     # NEW: Structural learning
│   ├── tenant_learning.py         # NEW: Tenant-level learning
│   └── unified_policy.py          # NEW: Unified policy framework
├── tests/
│   └── system_regression_suite.py # NEW: System regression
├── docs/
│   ├── SYSTEM_GAP_MAP.md          # NEW: Gap assessment
│   ├── DAG_EVOLUTION_LOG.md       # NEW: DAG evolution docs
│   ├── PLANNING_RATIONALE.md      # NEW: Planning docs
│   ├── LEARNING_EFFECT_REPORT.md  # NEW: Learning docs
│   └── ARCHITECTURE_DIAGRAM.md    # NEW: This file
└── artifacts/
    └── SYSTEM_HEALTH_REPORT.json  # NEW: Health report
```


