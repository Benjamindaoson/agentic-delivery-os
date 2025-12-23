# Planning Rationale

> System: Agentic AI Delivery OS
> Generated: 2025-12-22
> Component: `runtime/planning/llm_planner.py`

## Overview

This document describes the LLM-assisted planning system and the rationale behind its design decisions.

## Planning Philosophy

### 1. Goal-Driven, Not Rule-Driven

The planning system is designed to be **goal-driven** rather than purely rule-driven:

| Aspect | Rule-Driven (Old) | Goal-Driven (New) |
|--------|-------------------|-------------------|
| Decomposition | Fixed templates | LLM-assisted decomposition |
| Adaptation | Static plans | Replan on failure |
| Explainability | Implicit rules | Explicit rationale artifacts |
| Complexity Handling | One-size-fits-all | Complexity-based template selection |

### 2. Complexity-Based Template Selection

```
Task Complexity → Template Selection
──────────────────────────────────────
TRIVIAL         → linear_simple
SIMPLE          → linear_simple
MODERATE        → parallel_data
COMPLEX         → iterative_refinement
EXPERT          → hierarchical_decomposition
```

### 3. Replan Capability

When execution fails, the planner can generate a new plan:

```python
# Initial plan failed
decomposition, rationale = await planner.replan(
    run_id="original_run",
    original_goal="Build financial analysis dashboard",
    failure_info={
        "failure_type": "data_quality",
        "failed_node": "Data",
        "error": "Data source returned incomplete records"
    },
    context=updated_context
)
```

**Replan Strategies:**

| Failure Type | Replan Strategy |
|--------------|-----------------|
| Data issues | Switch to parallel_data template |
| Quality issues | Switch to iterative_refinement |
| Cost overrun | Switch to minimal_degraded |
| Timeout | Reduce parallelism |

## Complexity Assessment

The planner assesses task complexity using multiple signals:

### Input Signals

1. **Goal Length**: Short goals → simpler tasks
2. **Keyword Analysis**: 
   - "simple", "quick" → TRIVIAL
   - "find", "get" → SIMPLE
   - "analyze", "compare" → MODERATE
   - "build", "create" → COMPLEX
   - "optimize", "architect" → EXPERT

3. **Context Factors**:
   - Number of data sources
   - Presence of constraints
   - Historical context
   - Multi-step requirements

### Complexity Score Calculation

```python
complexity_scores = {}
for indicator in INDICATORS:
    if indicator in goal:
        complexity_scores[indicator.complexity] += 1

# Factor in context
if data_sources > 2: complexity_scores[MODERATE] += 1
if data_sources > 5: complexity_scores[COMPLEX] += 1
if multi_step_required: complexity_scores[COMPLEX] += 2

# Final complexity = max score
```

## Goal Decomposition

### LLM-Assisted Decomposition

When LLM is available, goals are decomposed using structured prompting:

```
Goal: "Build a financial analysis dashboard"

LLM Output:
{
  "subgoals": [
    {
      "subgoal_id": "sg_1",
      "description": "Validate data source availability",
      "success_criteria": ["All sources accessible", "Schema matches"],
      "dependencies": [],
      "assigned_agent": "DataAgent",
      "estimated_cost": 0.02,
      "risk_level": "low"
    },
    {
      "subgoal_id": "sg_2",
      "description": "Extract and transform financial data",
      "dependencies": ["sg_1"],
      "assigned_agent": "ExecutionAgent",
      ...
    }
  ],
  "decomposition_rationale": "Sequential approach for data reliability"
}
```

### Rule-Based Fallback

When LLM is unavailable, the system falls back to template-based decomposition:

```python
template = DAGTemplate.get_template("linear_simple")
subgoals = [
    Subgoal(
        subgoal_id=f"sg_{i}",
        description=AGENT_DESCRIPTIONS[node],
        assigned_agent=node,
        dependencies=DEPENDENCY_MAP[node]
    )
    for i, node in enumerate(template["nodes"])
]
```

## Artifact Generation

Every planning decision produces two artifacts:

### 1. goal_decomposition.json

```json
{
  "run_id": "run_abc123",
  "primary_goal": "Build financial analysis dashboard",
  "complexity": "complex",
  "subgoals": [...],
  "total_estimated_cost": 0.25,
  "total_estimated_latency_ms": 5000,
  "decomposition_rationale": "...",
  "llm_used": true,
  "llm_model": "qwen"
}
```

### 2. planning_rationale.md

```markdown
# Planning Rationale

**Run ID**: run_abc123
**Planning Mode**: initial
**Complexity**: complex

## DAG Template Selection

**Selected Template**: iterative_refinement

**Selection Reason**: Complex task requiring quality feedback loops

## Risk Assessment

- Multiple data sources may cause integration issues
- High complexity increases failure probability

## Constraints Applied

- Max cost: $1.00
- Max latency: 5000ms
```

## Integration with Execution

```
┌─────────────────┐
│  Goal Input     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LLM Planner     │ ← Complexity Assessment
│                 │ ← Template Selection
│                 │ ← Goal Decomposition
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Evolvable DAG   │ ← Plan Execution
│                 │ ← Runtime Mutations
└────────┬────────┘
         │
    Failure? ──Yes──▶ Replan
         │
         No
         │
         ▼
┌─────────────────┐
│ Completion      │
└─────────────────┘
```

## Future Enhancements

1. **Multi-objective Planning**: Optimize for cost/quality/latency simultaneously
2. **Hierarchical Decomposition**: Support nested sub-goal trees
3. **Collaborative Planning**: Multiple LLM agents for plan review
4. **Adaptive Templates**: Learn new templates from successful executions


