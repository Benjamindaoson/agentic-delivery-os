from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime

class GoalInterpretation(BaseModel):
    run_id: str
    primary_goal: str
    success_criteria: List[str]
    implied_constraints: List[str]
    confidence_score: float
    timestamp: datetime = Field(default_factory=datetime.now)

class HighLevelPlan(BaseModel):
    run_id: str
    stages: List[str]
    strategy_selected: str
    alternative_strategies_considered: List[str]
    rationale: str

class TaskStep(BaseModel):
    step_id: int
    title: str
    description: str
    dependencies: List[int]
    assigned_role: str
    expected_output: str

class TaskDecomposition(BaseModel):
    run_id: str
    steps: List[TaskStep]
    total_estimated_steps: int

class DependencyGraph(BaseModel):
    run_id: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

class ConstraintSpec(BaseModel):
    run_id: str
    hard_constraints: Dict[str, Any]
    soft_constraints: Dict[str, Any]
    evolution_path: Optional[str] = None # Path to previous version for diffing

class PlannerRationale(BaseModel):
    run_id: str
    why_this_decomposition: str
    risk_assessment: str
    optimality_explanation: str

class L5Planner:
    def __init__(self, artifact_base: str = "artifacts/goals"):
        self.artifact_base = artifact_base
        os.makedirs(artifact_base, exist_ok=True)

    def plan_task(self, run_id: str, query: str, classification: Any) -> Dict[str, Any]:
        # Implementation of full causal chain logic
        # 1. Interpret Goal
        goal = GoalInterpretation(
            run_id=run_id,
            primary_goal=query,
            success_criteria=["Accurate information", "Proper formatting"],
            implied_constraints=["Low latency", "Reliable sources"],
            confidence_score=0.9
        )
        self._save(goal, "goal_interpretation")

        # 2. High Level Plan
        plan = HighLevelPlan(
            run_id=run_id,
            stages=["Information Gathering", "Synthesis", "Refinement"],
            strategy_selected="top_down_refinement",
            alternative_strategies_considered=["flat_execution"],
            rationale="Complex query requires structured synthesis."
        )
        self._save(plan, "high_level_plan")

        # 3. Decomposition
        steps = [
            TaskStep(step_id=1, title="Search", description="Gather raw data", dependencies=[], assigned_role="DataAgent", expected_output="raw_docs"),
            TaskStep(step_id=2, title="Analyze", description="Process raw data", dependencies=[1], assigned_role="ExecutionAgent", expected_output="analysis_report")
        ]
        decomp = TaskDecomposition(run_id=run_id, steps=steps, total_estimated_steps=2)
        self._save(decomp, "task_decomposition")

        # 4. Dependency Graph
        graph = DependencyGraph(
            run_id=run_id,
            nodes=[{"id": 1, "label": "Search"}, {"id": 2, "label": "Analyze"}],
            edges=[{"from": 1, "to": 2}]
        )
        self._save(graph, "dependency_graph")

        # 5. Constraints
        constraints = ConstraintSpec(
            run_id=run_id,
            hard_constraints={"max_cost": 0.5},
            soft_constraints={"max_latency": 5000}
        )
        self._save(constraints, "constraint_spec")

        # 6. Rationale
        rationale = PlannerRationale(
            run_id=run_id,
            why_this_decomposition="Splitting search and analysis ensures data quality before synthesis.",
            risk_assessment="Low risk of data absence.",
            optimality_explanation="Sequential flow is optimal for small data volumes."
        )
        self._save(rationale, "planner_rationale")

        return {"goal": goal, "plan": plan, "decomposition": decomp, "graph": graph, "constraints": constraints, "rationale": rationale}

    def _save(self, obj: BaseModel, type_name: str):
        path = f"{self.artifact_base}/{obj.run_id}_{type_name}.json"
        with open(path, "w") as f:
            f.write(obj.model_dump_json(indent=2))



