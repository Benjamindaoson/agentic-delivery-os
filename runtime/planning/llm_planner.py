"""
LLM-Assisted Planner: Goal-driven planning with LLM support
P0-1 Implementation: Dynamic goal decomposition, replan capability, explainable artifacts

This planner:
1. Uses LLM to interpret goals and generate dynamic plans
2. Selects DAG templates based on task complexity
3. Supports replan on failure
4. Generates goal_decomposition.json and planning_rationale.md
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pydantic import BaseModel, Field

from runtime.llm.client_factory import create_llm_client
from runtime.llm.adapter import LLMAdapter


class TaskComplexity(str, Enum):
    """Task complexity levels for DAG template selection"""
    TRIVIAL = "trivial"      # Single agent, no decomposition
    SIMPLE = "simple"        # Linear DAG, 2-3 steps
    MODERATE = "moderate"    # Branching DAG, 4-6 steps
    COMPLEX = "complex"      # Full DAG with conditions, 7+ steps
    EXPERT = "expert"        # Nested sub-goals, iterative refinement


class PlanningMode(str, Enum):
    """Planning mode based on context"""
    INITIAL = "initial"      # First planning attempt
    REPLAN = "replan"        # Re-planning after failure
    REFINE = "refine"        # Refining existing plan
    MINIMAL = "minimal"      # Degraded mode, minimal plan


@dataclass
class Subgoal:
    """Decomposed subgoal from main goal"""
    subgoal_id: str
    description: str
    success_criteria: List[str]
    dependencies: List[str]  # IDs of prerequisite subgoals
    assigned_agent: str
    estimated_cost: float
    estimated_latency_ms: int
    risk_level: str
    rollback_strategy: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GoalDecomposition:
    """Complete goal decomposition artifact"""
    run_id: str
    primary_goal: str
    complexity: TaskComplexity
    subgoals: List[Subgoal]
    total_estimated_cost: float
    total_estimated_latency_ms: int
    decomposition_rationale: str
    llm_used: bool
    llm_model: Optional[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    schema_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["complexity"] = self.complexity.value
        result["subgoals"] = [s.to_dict() if isinstance(s, Subgoal) else s for s in self.subgoals]
        return result


@dataclass
class PlanningRationale:
    """Explainable planning rationale artifact"""
    run_id: str
    planning_mode: PlanningMode
    complexity_assessment: Dict[str, Any]
    dag_template_selected: str
    template_selection_reason: str
    alternative_templates_considered: List[str]
    risk_assessment: str
    optimality_explanation: str
    constraints_applied: List[str]
    llm_reasoning: Optional[str]
    replan_trigger: Optional[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["planning_mode"] = self.planning_mode.value
        return result
    
    def to_markdown(self) -> str:
        """Generate planning_rationale.md content"""
        md = f"""# Planning Rationale

**Run ID**: {self.run_id}  
**Planning Mode**: {self.planning_mode.value}  
**Created At**: {self.created_at}

## Complexity Assessment

| Dimension | Value |
|-----------|-------|
"""
        for dim, val in self.complexity_assessment.items():
            md += f"| {dim} | {val} |\n"
        
        md += f"""
## DAG Template Selection

**Selected Template**: {self.dag_template_selected}

**Selection Reason**: {self.template_selection_reason}

### Alternative Templates Considered

"""
        for alt in self.alternative_templates_considered:
            md += f"- {alt}\n"
        
        md += f"""
## Risk Assessment

{self.risk_assessment}

## Optimality Explanation

{self.optimality_explanation}

## Constraints Applied

"""
        for constraint in self.constraints_applied:
            md += f"- {constraint}\n"
        
        if self.llm_reasoning:
            md += f"""
## LLM Reasoning

{self.llm_reasoning}
"""
        
        if self.replan_trigger:
            md += f"""
## Replan Trigger

{self.replan_trigger}
"""
        
        return md


class DAGTemplate:
    """DAG template definition"""
    
    TEMPLATES = {
        "linear_simple": {
            "description": "Linear execution: Product → Data → Execution → Evaluation → Cost",
            "complexity": [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE],
            "nodes": ["Product", "Data", "Execution", "Evaluation", "Cost"],
            "edges": [("Product", "Data"), ("Data", "Execution"), 
                     ("Execution", "Evaluation"), ("Evaluation", "Cost")]
        },
        "parallel_data": {
            "description": "Parallel data gathering then sequential execution",
            "complexity": [TaskComplexity.MODERATE],
            "nodes": ["Product", "Data_Source1", "Data_Source2", "Data_Merge", 
                     "Execution", "Evaluation", "Cost"],
            "edges": [("Product", "Data_Source1"), ("Product", "Data_Source2"),
                     ("Data_Source1", "Data_Merge"), ("Data_Source2", "Data_Merge"),
                     ("Data_Merge", "Execution"), ("Execution", "Evaluation"),
                     ("Evaluation", "Cost")]
        },
        "iterative_refinement": {
            "description": "Iterative refinement with evaluation feedback loop",
            "complexity": [TaskComplexity.COMPLEX],
            "nodes": ["Product", "Data", "Execution", "Evaluation", 
                     "Refinement", "Final_Evaluation", "Cost"],
            "edges": [("Product", "Data"), ("Data", "Execution"),
                     ("Execution", "Evaluation"), ("Evaluation", "Refinement"),
                     ("Refinement", "Execution"), ("Evaluation", "Final_Evaluation"),
                     ("Final_Evaluation", "Cost")]
        },
        "hierarchical_decomposition": {
            "description": "Hierarchical decomposition with sub-tasks",
            "complexity": [TaskComplexity.EXPERT],
            "nodes": ["Product", "Planner", "SubTask1", "SubTask2", "SubTask3",
                     "Aggregator", "Evaluation", "Cost"],
            "edges": [("Product", "Planner"), ("Planner", "SubTask1"),
                     ("Planner", "SubTask2"), ("Planner", "SubTask3"),
                     ("SubTask1", "Aggregator"), ("SubTask2", "Aggregator"),
                     ("SubTask3", "Aggregator"), ("Aggregator", "Evaluation"),
                     ("Evaluation", "Cost")]
        },
        "minimal_degraded": {
            "description": "Minimal execution path for degraded mode",
            "complexity": [TaskComplexity.TRIVIAL],
            "nodes": ["Data", "Execution", "Cost"],
            "edges": [("Data", "Execution"), ("Execution", "Cost")]
        }
    }
    
    @classmethod
    def get_template(cls, template_id: str) -> Optional[Dict[str, Any]]:
        return cls.TEMPLATES.get(template_id)
    
    @classmethod
    def select_for_complexity(cls, complexity: TaskComplexity) -> str:
        """Select best template for given complexity"""
        for template_id, template in cls.TEMPLATES.items():
            if complexity in template["complexity"]:
                return template_id
        return "linear_simple"  # Default fallback


class LLMPlanner:
    """
    LLM-Assisted Planner with dynamic goal decomposition.
    
    Features:
    - LLM-based goal interpretation (falls back to rule-based if unavailable)
    - Dynamic DAG template selection based on complexity
    - Replan capability on failure
    - Explainable artifacts (goal_decomposition.json, planning_rationale.md)
    """
    
    # Complexity indicators from goal text
    COMPLEXITY_INDICATORS = {
        TaskComplexity.TRIVIAL: ["simple", "quick", "basic", "just"],
        TaskComplexity.SIMPLE: ["find", "get", "show", "list"],
        TaskComplexity.MODERATE: ["analyze", "compare", "evaluate", "summarize"],
        TaskComplexity.COMPLEX: ["design", "build", "create", "implement", "develop"],
        TaskComplexity.EXPERT: ["optimize", "architect", "refactor", "migrate", "transform"]
    }
    
    def __init__(
        self,
        artifacts_dir: str = "artifacts/planning",
        use_llm: bool = True,
        llm_model: str = "default"
    ):
        self.artifacts_dir = artifacts_dir
        self.use_llm = use_llm
        self.llm_model = llm_model
        
        # Create artifact directories
        os.makedirs(os.path.join(artifacts_dir, "decompositions"), exist_ok=True)
        os.makedirs(os.path.join(artifacts_dir, "rationales"), exist_ok=True)
        
        # Initialize LLM adapter (if available)
        self.llm_adapter: Optional[LLMAdapter] = None
        if use_llm:
            try:
                self.llm_adapter = LLMAdapter()
            except Exception:
                self.llm_adapter = None
    
    async def plan(
        self,
        run_id: str,
        goal: str,
        context: Dict[str, Any],
        previous_failure: Optional[Dict[str, Any]] = None
    ) -> Tuple[GoalDecomposition, PlanningRationale]:
        """
        Main planning entry point.
        
        Args:
            run_id: Unique run identifier
            goal: Primary goal description
            context: Execution context (constraints, history, etc.)
            previous_failure: Previous failure info for replan
            
        Returns:
            Tuple of (GoalDecomposition, PlanningRationale)
        """
        # Determine planning mode
        if previous_failure:
            planning_mode = PlanningMode.REPLAN
        elif context.get("refinement_requested"):
            planning_mode = PlanningMode.REFINE
        elif context.get("degraded_mode"):
            planning_mode = PlanningMode.MINIMAL
        else:
            planning_mode = PlanningMode.INITIAL
        
        # Assess complexity
        complexity, complexity_details = self._assess_complexity(goal, context)
        
        # Select DAG template
        template_id, template_reason, alternatives = self._select_dag_template(
            complexity, planning_mode, previous_failure
        )
        
        # Decompose goal
        if self.llm_adapter and self.use_llm:
            decomposition, llm_reasoning = await self._llm_decompose(
                run_id, goal, context, complexity, template_id
            )
        else:
            decomposition, llm_reasoning = self._rule_decompose(
                run_id, goal, context, complexity, template_id
            ), None
        
        # Generate rationale
        rationale = self._generate_rationale(
            run_id=run_id,
            planning_mode=planning_mode,
            complexity_details=complexity_details,
            template_id=template_id,
            template_reason=template_reason,
            alternatives=alternatives,
            context=context,
            llm_reasoning=llm_reasoning,
            previous_failure=previous_failure
        )
        
        # Save artifacts
        self._save_artifacts(decomposition, rationale)
        
        return decomposition, rationale
    
    def _assess_complexity(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> Tuple[TaskComplexity, Dict[str, Any]]:
        """Assess task complexity from goal and context"""
        goal_lower = goal.lower()
        details = {
            "goal_length": len(goal),
            "word_count": len(goal.split()),
            "has_constraints": bool(context.get("constraints")),
            "has_history": bool(context.get("history")),
            "data_sources": len(context.get("data_sources", [])),
            "indicator_matches": {}
        }
        
        # Check complexity indicators
        complexity_scores = {c: 0 for c in TaskComplexity}
        for complexity, indicators in self.COMPLEXITY_INDICATORS.items():
            for indicator in indicators:
                if indicator in goal_lower:
                    complexity_scores[complexity] += 1
                    details["indicator_matches"].setdefault(complexity.value, []).append(indicator)
        
        # Factor in context complexity
        if details["data_sources"] > 2:
            complexity_scores[TaskComplexity.MODERATE] += 1
        if details["data_sources"] > 5:
            complexity_scores[TaskComplexity.COMPLEX] += 1
        if context.get("multi_step_required"):
            complexity_scores[TaskComplexity.COMPLEX] += 2
        
        # Determine final complexity
        max_score = max(complexity_scores.values())
        if max_score == 0:
            # Default based on goal length
            if details["word_count"] < 5:
                complexity = TaskComplexity.TRIVIAL
            elif details["word_count"] < 15:
                complexity = TaskComplexity.SIMPLE
            else:
                complexity = TaskComplexity.MODERATE
        else:
            complexity = max(complexity_scores, key=complexity_scores.get)
        
        details["final_complexity"] = complexity.value
        details["complexity_scores"] = {k.value: v for k, v in complexity_scores.items()}
        
        return complexity, details
    
    def _select_dag_template(
        self,
        complexity: TaskComplexity,
        planning_mode: PlanningMode,
        previous_failure: Optional[Dict[str, Any]]
    ) -> Tuple[str, str, List[str]]:
        """Select appropriate DAG template"""
        alternatives = list(DAGTemplate.TEMPLATES.keys())
        
        # Handle special modes
        if planning_mode == PlanningMode.MINIMAL:
            return "minimal_degraded", "Degraded mode requested", alternatives
        
        if planning_mode == PlanningMode.REPLAN and previous_failure:
            # Adjust template based on failure type
            failure_type = previous_failure.get("failure_type", "")
            if "data" in failure_type.lower():
                return "parallel_data", f"Replan: parallel data to avoid {failure_type}", alternatives
            if "quality" in failure_type.lower():
                return "iterative_refinement", f"Replan: refinement for quality issue", alternatives
        
        # Normal template selection
        template_id = DAGTemplate.select_for_complexity(complexity)
        template = DAGTemplate.get_template(template_id)
        reason = f"Selected for {complexity.value} complexity: {template['description']}"
        
        return template_id, reason, [a for a in alternatives if a != template_id]
    
    async def _llm_decompose(
        self,
        run_id: str,
        goal: str,
        context: Dict[str, Any],
        complexity: TaskComplexity,
        template_id: str
    ) -> Tuple[GoalDecomposition, str]:
        """Use LLM to decompose goal into subgoals"""
        template = DAGTemplate.get_template(template_id)
        
        # Build LLM prompt
        prompt = f"""You are a task planning assistant. Decompose the following goal into subgoals.

GOAL: {goal}

COMPLEXITY LEVEL: {complexity.value}

DAG TEMPLATE: {template_id}
Template structure: {template['description']}
Template nodes: {', '.join(template['nodes'])}

CONTEXT:
- Constraints: {json.dumps(context.get('constraints', {}), indent=2)}
- Available data sources: {context.get('data_sources', [])}

Please provide a JSON decomposition with the following structure:
{{
    "subgoals": [
        {{
            "subgoal_id": "sg_1",
            "description": "Description of the subgoal",
            "success_criteria": ["criterion 1", "criterion 2"],
            "dependencies": [],
            "assigned_agent": "AgentName",
            "estimated_cost": 0.05,
            "estimated_latency_ms": 1000,
            "risk_level": "low|medium|high",
            "rollback_strategy": "How to rollback if this fails"
        }}
    ],
    "decomposition_rationale": "Why this decomposition makes sense",
    "reasoning": "Step-by-step reasoning for the decomposition"
}}
"""
        
        schema = {
            "type": "object",
            "properties": {
                "subgoals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subgoal_id": {"type": "string"},
                            "description": {"type": "string"},
                            "success_criteria": {"type": "array", "items": {"type": "string"}},
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "assigned_agent": {"type": "string"},
                            "estimated_cost": {"type": "number"},
                            "estimated_latency_ms": {"type": "integer"},
                            "risk_level": {"type": "string"},
                            "rollback_strategy": {"type": "string"}
                        },
                        "required": ["subgoal_id", "description", "assigned_agent"]
                    }
                },
                "decomposition_rationale": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["subgoals", "decomposition_rationale"]
        }
        
        try:
            system_prompt = "You are a task planning assistant. Decompose goals into structured subgoals."
            result, meta = await self.llm_adapter.call(
                system_prompt=system_prompt,
                user_prompt=prompt,
                schema=schema,
                task_id=run_id
            )
            
            # Parse subgoals
            subgoals = []
            for sg in result.get("subgoals", []):
                subgoals.append(Subgoal(
                    subgoal_id=sg.get("subgoal_id", f"sg_{len(subgoals)+1}"),
                    description=sg.get("description", ""),
                    success_criteria=sg.get("success_criteria", []),
                    dependencies=sg.get("dependencies", []),
                    assigned_agent=sg.get("assigned_agent", "Execution"),
                    estimated_cost=sg.get("estimated_cost", 0.05),
                    estimated_latency_ms=sg.get("estimated_latency_ms", 1000),
                    risk_level=sg.get("risk_level", "low"),
                    rollback_strategy=sg.get("rollback_strategy")
                ))
            
            # Calculate totals
            total_cost = sum(sg.estimated_cost for sg in subgoals)
            total_latency = sum(sg.estimated_latency_ms for sg in subgoals)
            
            decomposition = GoalDecomposition(
                run_id=run_id,
                primary_goal=goal,
                complexity=complexity,
                subgoals=subgoals,
                total_estimated_cost=total_cost,
                total_estimated_latency_ms=total_latency,
                decomposition_rationale=result.get("decomposition_rationale", "LLM-generated decomposition"),
                llm_used=True,
                llm_model=self.llm_model
            )
            
            return decomposition, result.get("reasoning", "")
            
        except Exception as e:
            # Fallback to rule-based
            return self._rule_decompose(run_id, goal, context, complexity, template_id), f"LLM failed: {e}, using rule-based"
    
    def _rule_decompose(
        self,
        run_id: str,
        goal: str,
        context: Dict[str, Any],
        complexity: TaskComplexity,
        template_id: str
    ) -> GoalDecomposition:
        """Rule-based goal decomposition (fallback)"""
        template = DAGTemplate.get_template(template_id)
        
        # Map template nodes to subgoals
        agent_descriptions = {
            "Product": "Validate goal feasibility and constraints",
            "Data": "Gather and prepare required data",
            "Data_Source1": "Gather primary data source",
            "Data_Source2": "Gather secondary data source",
            "Data_Merge": "Merge and reconcile data sources",
            "Execution": "Execute core task logic",
            "Evaluation": "Evaluate execution quality",
            "Final_Evaluation": "Final quality check",
            "Cost": "Cost accounting and budget check",
            "Planner": "Plan sub-task decomposition",
            "SubTask1": "Execute sub-task 1",
            "SubTask2": "Execute sub-task 2",
            "SubTask3": "Execute sub-task 3",
            "Aggregator": "Aggregate sub-task results",
            "Refinement": "Refine based on evaluation feedback"
        }
        
        # Build dependency map from edges
        deps_map = {}
        for src, tgt in template.get("edges", []):
            deps_map.setdefault(tgt, []).append(src)
        
        subgoals = []
        for i, node in enumerate(template["nodes"]):
            subgoals.append(Subgoal(
                subgoal_id=f"sg_{i+1}",
                description=agent_descriptions.get(node, f"Execute {node} step"),
                success_criteria=[f"{node} completed successfully"],
                dependencies=[f"sg_{template['nodes'].index(d)+1}" 
                             for d in deps_map.get(node, [])],
                assigned_agent=node.replace("_", ""),
                estimated_cost=0.05,
                estimated_latency_ms=1000,
                risk_level="low"
            ))
        
        total_cost = sum(sg.estimated_cost for sg in subgoals)
        total_latency = sum(sg.estimated_latency_ms for sg in subgoals)
        
        return GoalDecomposition(
            run_id=run_id,
            primary_goal=goal,
            complexity=complexity,
            subgoals=subgoals,
            total_estimated_cost=total_cost,
            total_estimated_latency_ms=total_latency,
            decomposition_rationale=f"Rule-based decomposition using {template_id} template",
            llm_used=False,
            llm_model=None
        )
    
    def _generate_rationale(
        self,
        run_id: str,
        planning_mode: PlanningMode,
        complexity_details: Dict[str, Any],
        template_id: str,
        template_reason: str,
        alternatives: List[str],
        context: Dict[str, Any],
        llm_reasoning: Optional[str],
        previous_failure: Optional[Dict[str, Any]]
    ) -> PlanningRationale:
        """Generate explainable planning rationale"""
        
        # Risk assessment
        risk_factors = []
        if complexity_details.get("data_sources", 0) > 3:
            risk_factors.append("Multiple data sources may cause integration issues")
        if complexity_details.get("final_complexity") in ["complex", "expert"]:
            risk_factors.append("High complexity increases failure probability")
        if previous_failure:
            risk_factors.append(f"Previous failure: {previous_failure.get('failure_type')}")
        
        risk_assessment = "\n".join(f"- {r}" for r in risk_factors) if risk_factors else "Low risk profile"
        
        # Constraints applied
        constraints = []
        if context.get("max_cost"):
            constraints.append(f"Max cost: ${context['max_cost']}")
        if context.get("max_latency_ms"):
            constraints.append(f"Max latency: {context['max_latency_ms']}ms")
        if context.get("required_agents"):
            constraints.append(f"Required agents: {', '.join(context['required_agents'])}")
        
        # Optimality explanation
        template = DAGTemplate.get_template(template_id)
        optimality = f"""Selected {template_id} template because:
1. {template['description']}
2. Matches complexity level: {complexity_details.get('final_complexity', 'unknown')}
3. Node count ({len(template['nodes'])}) appropriate for estimated workload
4. Supports required execution patterns"""
        
        return PlanningRationale(
            run_id=run_id,
            planning_mode=planning_mode,
            complexity_assessment=complexity_details,
            dag_template_selected=template_id,
            template_selection_reason=template_reason,
            alternative_templates_considered=alternatives,
            risk_assessment=risk_assessment,
            optimality_explanation=optimality,
            constraints_applied=constraints or ["No explicit constraints"],
            llm_reasoning=llm_reasoning,
            replan_trigger=previous_failure.get("failure_type") if previous_failure else None
        )
    
    def _save_artifacts(
        self,
        decomposition: GoalDecomposition,
        rationale: PlanningRationale
    ):
        """Save planning artifacts"""
        run_id = decomposition.run_id
        
        # Save goal_decomposition.json
        decomp_path = os.path.join(
            self.artifacts_dir, "decompositions", f"{run_id}_goal_decomposition.json"
        )
        with open(decomp_path, "w", encoding="utf-8") as f:
            json.dump(decomposition.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Save planning_rationale.md
        rationale_path = os.path.join(
            self.artifacts_dir, "rationales", f"{run_id}_planning_rationale.md"
        )
        with open(rationale_path, "w", encoding="utf-8") as f:
            f.write(rationale.to_markdown())
        
        # Also save rationale as JSON for machine processing
        rationale_json_path = os.path.join(
            self.artifacts_dir, "rationales", f"{run_id}_planning_rationale.json"
        )
        with open(rationale_json_path, "w", encoding="utf-8") as f:
            json.dump(rationale.to_dict(), f, indent=2, ensure_ascii=False)
    
    async def replan(
        self,
        run_id: str,
        original_goal: str,
        failure_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[GoalDecomposition, PlanningRationale]:
        """
        Replan after failure.
        
        Args:
            run_id: Original run ID (will generate new ID for replan)
            original_goal: Original goal
            failure_info: Information about the failure
            context: Updated context
            
        Returns:
            New decomposition and rationale
        """
        replan_run_id = f"{run_id}_replan_{datetime.now().strftime('%H%M%S')}"
        return await self.plan(
            run_id=replan_run_id,
            goal=original_goal,
            context=context,
            previous_failure=failure_info
        )


# Global LLM planner instance
_llm_planner: Optional[LLMPlanner] = None

def get_llm_planner() -> LLMPlanner:
    """Get global LLM planner instance"""
    global _llm_planner
    if _llm_planner is None:
        _llm_planner = LLMPlanner()
    return _llm_planner

