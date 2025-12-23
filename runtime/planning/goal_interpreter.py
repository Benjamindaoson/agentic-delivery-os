"""
Goal Interpreter: Parse task input + context into structured goal artifacts.
L5-grade: All goals are explicit, machine-checkable, artifact-driven.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class GoalType(str, Enum):
    """Types of goals the system can pursue."""
    ANSWER = "answer"  # Provide an answer to a question
    TRANSFORM = "transform"  # Transform data from one form to another
    DECIDE = "decide"  # Make a decision between alternatives
    EXPLORE = "explore"  # Explore a space to gather information
    CREATE = "create"  # Create new content/artifact
    VALIDATE = "validate"  # Validate existing content
    SUMMARIZE = "summarize"  # Summarize information


class ConstraintType(str, Enum):
    """Constraint severity levels."""
    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Should be satisfied if possible


@dataclass
class SuccessCriterion:
    """Machine-checkable success criterion."""
    criterion_id: str
    description: str
    check_type: str  # regex, threshold, contains, exact, semantic
    check_value: Any
    weight: float = 1.0
    required: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Constraint:
    """Goal constraint."""
    constraint_id: str
    constraint_type: ConstraintType
    description: str
    scope: str  # cost, latency, quality, safety
    threshold: Optional[float] = None
    value: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["constraint_type"] = self.constraint_type.value
        return result


@dataclass
class OptimizationTarget:
    """Optimization target for the goal."""
    target_id: str
    dimension: str  # quality, cost, latency, coverage
    direction: str  # maximize, minimize
    weight: float = 1.0
    baseline: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UncertaintyFactor:
    """Factor contributing to goal uncertainty."""
    factor_id: str
    source: str  # input, context, retrieval, tool, model
    description: str
    estimated_impact: float  # 0.0-1.0
    mitigation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Goal:
    """Structured goal representation."""
    goal_id: str
    run_id: str
    goal_type: GoalType
    description: str
    success_criteria: List[SuccessCriterion]
    constraints: List[Constraint]
    optimization_targets: List[OptimizationTarget]
    uncertainty_factors: List[UncertaintyFactor]
    context_hash: str = ""
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "run_id": self.run_id,
            "goal_type": self.goal_type.value,
            "description": self.description,
            "success_criteria": [c.to_dict() for c in self.success_criteria],
            "constraints": [c.to_dict() for c in self.constraints],
            "optimization_targets": [t.to_dict() for t in self.optimization_targets],
            "uncertainty_factors": [f.to_dict() for f in self.uncertainty_factors],
            "context_hash": self.context_hash,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }
    
    def to_hash(self) -> str:
        """Generate deterministic hash for replay."""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class GoalInterpreter:
    """
    Interprets task input and context into structured goals.
    
    All goals are:
    - Explicit (no implicit assumptions)
    - Machine-checkable (success criteria are verifiable)
    - Artifact-driven (saved to artifacts/goals/)
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.goals_dir = os.path.join(artifacts_dir, "goals")
        os.makedirs(self.goals_dir, exist_ok=True)
    
    def interpret(
        self,
        run_id: str,
        task_input: Dict[str, Any],
        context_snapshot: Optional[Dict[str, Any]] = None
    ) -> Goal:
        """
        Interpret task input into a structured goal.
        
        Args:
            run_id: Run identifier
            task_input: Raw task input (query, intent, etc.)
            context_snapshot: Optional context (history, state, etc.)
            
        Returns:
            Goal object
        """
        # Generate goal ID
        goal_id = self._generate_goal_id(run_id, task_input)
        
        # Determine goal type
        goal_type = self._classify_goal_type(task_input)
        
        # Extract description
        description = self._extract_description(task_input)
        
        # Build success criteria
        success_criteria = self._build_success_criteria(task_input, goal_type)
        
        # Extract constraints
        constraints = self._extract_constraints(task_input)
        
        # Define optimization targets
        optimization_targets = self._define_optimization_targets(task_input, goal_type)
        
        # Identify uncertainty factors
        uncertainty_factors = self._identify_uncertainties(task_input, context_snapshot)
        
        # Compute context hash
        context_hash = self._hash_context(context_snapshot) if context_snapshot else ""
        
        goal = Goal(
            goal_id=goal_id,
            run_id=run_id,
            goal_type=goal_type,
            description=description,
            success_criteria=success_criteria,
            constraints=constraints,
            optimization_targets=optimization_targets,
            uncertainty_factors=uncertainty_factors,
            context_hash=context_hash
        )
        
        # Save artifact
        self._save_goal(goal)
        
        return goal
    
    def load_goal(self, run_id: str) -> Optional[Goal]:
        """Load goal from artifact."""
        path = os.path.join(self.goals_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_goal(data)
    
    def _generate_goal_id(self, run_id: str, task_input: Dict[str, Any]) -> str:
        """Generate unique goal ID."""
        content = f"{run_id}:{json.dumps(task_input, sort_keys=True)}"
        return f"goal_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _classify_goal_type(self, task_input: Dict[str, Any]) -> GoalType:
        """Classify goal type based on task input."""
        query = task_input.get("query", "").lower()
        intent = task_input.get("intent", "").lower()
        
        # Heuristic classification
        if any(kw in query for kw in ["what is", "who is", "when", "where", "why", "how"]):
            return GoalType.ANSWER
        if any(kw in query for kw in ["convert", "transform", "change"]):
            return GoalType.TRANSFORM
        if any(kw in query for kw in ["should", "decide", "choose", "compare"]):
            return GoalType.DECIDE
        if any(kw in query for kw in ["explore", "find", "search", "discover"]):
            return GoalType.EXPLORE
        if any(kw in query for kw in ["create", "generate", "write", "build"]):
            return GoalType.CREATE
        if any(kw in query for kw in ["validate", "verify", "check"]):
            return GoalType.VALIDATE
        if any(kw in query for kw in ["summarize", "summary", "brief"]):
            return GoalType.SUMMARIZE
        
        # Default based on intent
        if intent:
            try:
                return GoalType(intent)
            except ValueError:
                pass
        
        return GoalType.ANSWER
    
    def _extract_description(self, task_input: Dict[str, Any]) -> str:
        """Extract goal description from task input."""
        return task_input.get("query", task_input.get("description", "Unspecified goal"))
    
    def _build_success_criteria(
        self,
        task_input: Dict[str, Any],
        goal_type: GoalType
    ) -> List[SuccessCriterion]:
        """Build machine-checkable success criteria."""
        criteria = []
        
        # Default criteria based on goal type
        if goal_type == GoalType.ANSWER:
            criteria.append(SuccessCriterion(
                criterion_id="answer_present",
                description="Response contains a direct answer",
                check_type="contains",
                check_value=["because", "is", "are", "the answer"],
                weight=1.0,
                required=True
            ))
            criteria.append(SuccessCriterion(
                criterion_id="evidence_cited",
                description="Response cites evidence",
                check_type="threshold",
                check_value={"min_citations": 1},
                weight=0.8,
                required=False
            ))
        
        elif goal_type == GoalType.TRANSFORM:
            criteria.append(SuccessCriterion(
                criterion_id="output_format_valid",
                description="Output matches expected format",
                check_type="schema",
                check_value=task_input.get("output_schema", {}),
                weight=1.0,
                required=True
            ))
        
        elif goal_type == GoalType.DECIDE:
            criteria.append(SuccessCriterion(
                criterion_id="decision_stated",
                description="A clear decision is stated",
                check_type="contains",
                check_value=["recommend", "suggest", "choose", "decision"],
                weight=1.0,
                required=True
            ))
            criteria.append(SuccessCriterion(
                criterion_id="rationale_provided",
                description="Decision rationale is provided",
                check_type="threshold",
                check_value={"min_length": 50},
                weight=0.9,
                required=True
            ))
        
        # Add custom criteria from input
        for custom in task_input.get("success_criteria", []):
            criteria.append(SuccessCriterion(
                criterion_id=custom.get("id", f"custom_{len(criteria)}"),
                description=custom.get("description", "Custom criterion"),
                check_type=custom.get("check_type", "contains"),
                check_value=custom.get("check_value"),
                weight=custom.get("weight", 1.0),
                required=custom.get("required", False)
            ))
        
        return criteria
    
    def _extract_constraints(self, task_input: Dict[str, Any]) -> List[Constraint]:
        """Extract constraints from task input."""
        constraints = []
        
        # Cost constraint
        max_cost = task_input.get("max_cost")
        if max_cost:
            constraints.append(Constraint(
                constraint_id="cost_limit",
                constraint_type=ConstraintType.HARD,
                description="Maximum cost limit",
                scope="cost",
                threshold=float(max_cost)
            ))
        
        # Latency constraint
        max_latency = task_input.get("max_latency_ms")
        if max_latency:
            constraints.append(Constraint(
                constraint_id="latency_limit",
                constraint_type=ConstraintType.SOFT,
                description="Maximum latency limit",
                scope="latency",
                threshold=float(max_latency)
            ))
        
        # Quality constraint
        min_quality = task_input.get("min_quality")
        if min_quality:
            constraints.append(Constraint(
                constraint_id="quality_floor",
                constraint_type=ConstraintType.HARD,
                description="Minimum quality threshold",
                scope="quality",
                threshold=float(min_quality)
            ))
        
        # Custom constraints
        for custom in task_input.get("constraints", []):
            constraints.append(Constraint(
                constraint_id=custom.get("id", f"custom_{len(constraints)}"),
                constraint_type=ConstraintType(custom.get("type", "soft")),
                description=custom.get("description", "Custom constraint"),
                scope=custom.get("scope", "other"),
                threshold=custom.get("threshold"),
                value=custom.get("value")
            ))
        
        return constraints
    
    def _define_optimization_targets(
        self,
        task_input: Dict[str, Any],
        goal_type: GoalType
    ) -> List[OptimizationTarget]:
        """Define optimization targets."""
        targets = []
        
        # Quality (always)
        targets.append(OptimizationTarget(
            target_id="quality",
            dimension="quality",
            direction="maximize",
            weight=1.0
        ))
        
        # Cost (minimize)
        if task_input.get("optimize_cost", True):
            targets.append(OptimizationTarget(
                target_id="cost",
                dimension="cost",
                direction="minimize",
                weight=0.5
            ))
        
        # Latency (minimize)
        if task_input.get("optimize_latency", True):
            targets.append(OptimizationTarget(
                target_id="latency",
                dimension="latency",
                direction="minimize",
                weight=0.3
            ))
        
        # Coverage (for explore/answer)
        if goal_type in [GoalType.EXPLORE, GoalType.ANSWER]:
            targets.append(OptimizationTarget(
                target_id="coverage",
                dimension="coverage",
                direction="maximize",
                weight=0.4
            ))
        
        return targets
    
    def _identify_uncertainties(
        self,
        task_input: Dict[str, Any],
        context_snapshot: Optional[Dict[str, Any]]
    ) -> List[UncertaintyFactor]:
        """Identify uncertainty factors."""
        factors = []
        
        # Input ambiguity
        query = task_input.get("query", "")
        if len(query) < 20:
            factors.append(UncertaintyFactor(
                factor_id="short_query",
                source="input",
                description="Query is short, may be ambiguous",
                estimated_impact=0.3,
                mitigation="Request clarification or expand context"
            ))
        
        # Missing context
        if not context_snapshot:
            factors.append(UncertaintyFactor(
                factor_id="no_context",
                source="context",
                description="No context provided",
                estimated_impact=0.2,
                mitigation="Use default assumptions"
            ))
        
        # Domain uncertainty
        if task_input.get("domain_uncertain", False):
            factors.append(UncertaintyFactor(
                factor_id="domain_uncertain",
                source="input",
                description="Domain or topic is uncertain",
                estimated_impact=0.4,
                mitigation="Broaden retrieval scope"
            ))
        
        return factors
    
    def _hash_context(self, context: Dict[str, Any]) -> str:
        """Hash context for replay."""
        content = json.dumps(context, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def _save_goal(self, goal: Goal) -> None:
        """Save goal to artifact."""
        path = os.path.join(self.goals_dir, f"{goal.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(goal.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_goal(self, data: Dict[str, Any]) -> Goal:
        """Convert dict to Goal object."""
        return Goal(
            goal_id=data["goal_id"],
            run_id=data["run_id"],
            goal_type=GoalType(data["goal_type"]),
            description=data["description"],
            success_criteria=[
                SuccessCriterion(**c) for c in data["success_criteria"]
            ],
            constraints=[
                Constraint(
                    constraint_id=c["constraint_id"],
                    constraint_type=ConstraintType(c["constraint_type"]),
                    description=c["description"],
                    scope=c["scope"],
                    threshold=c.get("threshold"),
                    value=c.get("value")
                )
                for c in data["constraints"]
            ],
            optimization_targets=[
                OptimizationTarget(**t) for t in data["optimization_targets"]
            ],
            uncertainty_factors=[
                UncertaintyFactor(**f) for f in data["uncertainty_factors"]
            ],
            context_hash=data.get("context_hash", ""),
            created_at=data.get("created_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



