# DAG Evolution Log

> System: Agentic AI Delivery OS
> Generated: 2025-12-22
> Component: `runtime/execution_graph/evolvable_dag.py`

## Overview

This document describes the DAG evolution capabilities implemented in the system. The Evolvable DAG supports runtime modifications including node injection, removal, skip, merge, and reordering—all with full artifact tracking for replay and rollback.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      EvolvableDAG                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   DAGNode   │───▶│   DAGNode   │───▶│   DAGNode   │         │
│  │  (Product)  │    │   (Data)    │    │ (Execution) │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│        │                  │                  │                  │
│        │                  │                  │                  │
│        ▼                  ▼                  ▼                  │
│  ┌───────────────────────────────────────────────────────┐     │
│  │                  Mutation History                      │     │
│  │  [inject_node, skip_node, merge_nodes, reorder, ...]  │     │
│  └───────────────────────────────────────────────────────┘     │
│        │                                                        │
│        ▼                                                        │
│  ┌───────────────────────────────────────────────────────┐     │
│  │                    Snapshots                           │     │
│  │  [snap_0001, snap_0002, ...] → Rollback Support        │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Mutation Types

| Type | Description | Reversible |
|------|-------------|------------|
| `NODE_INJECT` | Add new node at runtime | ✅ |
| `NODE_REMOVE` | Remove node and rewire dependencies | ✅ |
| `NODE_SKIP` | Mark node as skipped (keep in DAG) | ✅ |
| `NODE_MERGE` | Merge multiple nodes into one | ✅ |
| `NODE_SPLIT` | Split one node into multiple | ✅ |
| `EDGE_ADD` | Add dependency edge | ✅ |
| `EDGE_REMOVE` | Remove dependency edge | ✅ |
| `REORDER` | Change node execution order | ✅ |
| `CONDITION_UPDATE` | Update node execution condition | ✅ |
| `PLAN_SWITCH` | Switch to different execution plan | ❌ |

## Key Features

### 1. Node Injection

```python
dag.inject_node(
    node=DAGNode(
        node_id="validation_step",
        agent_name="ValidationAgent",
        description="Runtime validation"
    ),
    after_node_id="Execution",
    reason="quality_degradation_detected"
)
```

**Behavior:**
- Node is inserted into the DAG
- Edges are automatically rewired
- Dependents of the target node now depend on the new node
- Mutation is recorded for audit

### 2. Node Skip

```python
dag.skip_node(
    node_id="optional_analysis",
    reason="budget_constraint"
)
```

**Behavior:**
- Node remains in DAG but status is `SKIPPED`
- Execution engine will not execute the node
- Dependencies are preserved for structural integrity

### 3. Node Merge

```python
dag.merge_nodes(
    source_node_ids=["DataSource1", "DataSource2"],
    merged_node=DAGNode(
        node_id="MergedData",
        agent_name="DataMergeAgent"
    ),
    reason="parallel_data_optimization"
)
```

**Behavior:**
- Source nodes marked as `MERGED`
- New merged node inherits all dependencies
- All dependents now depend on merged node

### 4. Rollback

```python
# Take snapshot before risky operation
snapshot = dag._take_snapshot()

# Perform operation
dag.inject_node(...)

# If something goes wrong
dag.rollback_to_snapshot(snapshot.snapshot_id)
```

## Artifact Output

Each DAG execution produces:

```
artifacts/dag_evolution/{run_id}_dag_evolution.json
```

**Contents:**
```json
{
  "dag_id": "dag_linear_simple_abc123",
  "run_id": "run_abc123",
  "final_state": {
    "nodes": [...],
    "edges": [...],
    "hash": "a1b2c3d4e5f6"
  },
  "mutations": [
    {
      "mutation_id": "mut_0001",
      "mutation_type": "node_inject",
      "timestamp": "2025-12-22T10:00:00",
      "trigger": "quality_degradation",
      "before_hash": "...",
      "after_hash": "...",
      "reversible": true
    }
  ],
  "snapshots": [...],
  "statistics": {
    "total_mutations": 3,
    "nodes_added": 1,
    "nodes_skipped": 1,
    "reorders": 1
  }
}
```

## Learning Integration

The DAG evolution system integrates with structural learning:

```python
from learning.structural_learning import get_structural_learner

# After execution
learner = get_structural_learner()
learner.record_execution(
    task_type="analyze",
    structure_vector=structure_vector,
    reward=reward,
    credit_assignment=credit_assignment
)

# Get recommendation for future tasks
recommendation = learner.recommend_structure(
    task_type="analyze",
    available_templates=["linear_simple", "parallel_data"],
    complexity="moderate"
)
```

## Templates

### linear_simple
```
Product → Data → Execution → Evaluation → Cost
```

### parallel_data
```
        ┌─▶ Data_Source1 ─┐
Product ┤                 ├─▶ Data_Merge → Execution → Evaluation → Cost
        └─▶ Data_Source2 ─┘
```

### iterative_refinement
```
Product → Data → Execution → Evaluation
                     ▲           │
                     │           ▼
                     └── Refinement
                              │
                              ▼
                       Final_Evaluation → Cost
```

### hierarchical_decomposition
```
Product → Planner ─┬─▶ SubTask1 ─┐
                   ├─▶ SubTask2 ─┼─▶ Aggregator → Evaluation → Cost
                   └─▶ SubTask3 ─┘
```

## Best Practices

1. **Always take snapshots** before risky mutations
2. **Record mutation reasons** for audit
3. **Use conditions** instead of removal when possible
4. **Monitor evolution statistics** for drift detection
5. **Link to learning** for continuous improvement


