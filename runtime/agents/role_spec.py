"""
Role Specification: Decouple roles from planner, enable dynamic attachment.
L5-grade: Roles are explicit, evolvable via Learning signals.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class RoleRequirement:
    """Requirement for a role."""
    requirement_id: str
    description: str
    required: bool = True
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RolePermission:
    """Permission granted to a role."""
    permission_id: str
    resource: str  # tool, data, agent, system
    action: str  # read, write, execute, invoke
    scope: str  # all, limited, specific
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoleSpec:
    """Role specification - decoupled from specific agents."""
    role_id: str
    role_name: str
    description: str
    
    # What the role requires
    input_requirements: List[RoleRequirement]
    output_requirements: List[RoleRequirement]
    
    # What the role can do
    permissions: List[RolePermission]
    
    # Constraints
    max_retries: int = 3
    timeout_ms: int = 30000
    priority: int = 5  # 1-10
    
    # Evolution
    learning_signals_consumed: List[str] = field(default_factory=list)
    learning_signals_produced: List[str] = field(default_factory=list)
    
    # Metadata
    version: str = "1.0"
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "description": self.description,
            "input_requirements": [r.to_dict() for r in self.input_requirements],
            "output_requirements": [r.to_dict() for r in self.output_requirements],
            "permissions": [p.to_dict() for p in self.permissions],
            "max_retries": self.max_retries,
            "timeout_ms": self.timeout_ms,
            "priority": self.priority,
            "learning_signals_consumed": self.learning_signals_consumed,
            "learning_signals_produced": self.learning_signals_produced,
            "version": self.version,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }


@dataclass
class RoleAssignment:
    """Assignment of a role to a specific run/task."""
    assignment_id: str
    run_id: str
    role_id: str
    agent_id: str
    task_type: str
    
    # Assignment context
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Execution constraints (may override role defaults)
    override_max_retries: Optional[int] = None
    override_timeout_ms: Optional[int] = None
    override_priority: Optional[int] = None
    
    # Outcome tracking
    status: str = "assigned"  # assigned, active, completed, failed
    outcome: Optional[Dict[str, Any]] = None
    
    # Metadata
    assigned_at: str = ""
    completed_at: Optional[str] = None
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.assigned_at:
            self.assigned_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RoleSpecRegistry:
    """
    Registry of role specifications.
    
    Roles are decoupled from planner and can be:
    - Attached to tasks dynamically
    - Evolved via Learning signals
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.roles_dir = os.path.join(artifacts_dir, "agents", "roles")
        self.assignments_dir = os.path.join(artifacts_dir, "agents", "role_assignments")
        os.makedirs(self.roles_dir, exist_ok=True)
        os.makedirs(self.assignments_dir, exist_ok=True)
        
        self._roles: Dict[str, RoleSpec] = {}
        self._register_default_roles()
    
    def _register_default_roles(self) -> None:
        """Register default roles."""
        # Retriever Role
        self.register(RoleSpec(
            role_id="retriever",
            role_name="Retriever",
            description="Retrieves relevant information from knowledge sources",
            input_requirements=[
                RoleRequirement("query", "Search query or intent", required=True),
                RoleRequirement("sources", "Data sources to query", required=True)
            ],
            output_requirements=[
                RoleRequirement("documents", "Retrieved documents", required=True),
                RoleRequirement("relevance_scores", "Relevance scores", required=False)
            ],
            permissions=[
                RolePermission("read_data", "data", "read", "limited"),
                RolePermission("invoke_retriever", "tool", "execute", "specific", {"tools": ["retriever", "embedder"]})
            ],
            learning_signals_consumed=["retrieval_policy_update"],
            learning_signals_produced=["retrieval_quality_score", "coverage_score"]
        ))
        
        # Generator Role
        self.register(RoleSpec(
            role_id="generator",
            role_name="Generator",
            description="Generates output based on context and instructions",
            input_requirements=[
                RoleRequirement("context", "Context for generation", required=True),
                RoleRequirement("instructions", "Generation instructions", required=True)
            ],
            output_requirements=[
                RoleRequirement("output", "Generated output", required=True),
                RoleRequirement("confidence", "Generation confidence", required=False)
            ],
            permissions=[
                RolePermission("invoke_llm", "tool", "execute", "specific", {"tools": ["llm_client"]}),
                RolePermission("read_prompt", "data", "read", "specific", {"type": "prompt_templates"})
            ],
            learning_signals_consumed=["prompt_policy_update"],
            learning_signals_produced=["generation_quality_score", "hallucination_risk"]
        ))
        
        # Validator Role
        self.register(RoleSpec(
            role_id="validator",
            role_name="Validator",
            description="Validates outputs against criteria",
            input_requirements=[
                RoleRequirement("content", "Content to validate", required=True),
                RoleRequirement("criteria", "Validation criteria", required=True)
            ],
            output_requirements=[
                RoleRequirement("valid", "Validation result", required=True),
                RoleRequirement("violations", "List of violations", required=False)
            ],
            permissions=[
                RolePermission("invoke_validator", "tool", "execute", "specific", {"tools": ["validator", "schema_checker"]})
            ],
            learning_signals_consumed=["validation_rule_update"],
            learning_signals_produced=["validation_accuracy"]
        ))
        
        # Planner Role
        self.register(RoleSpec(
            role_id="planner",
            role_name="Planner",
            description="Plans execution strategy and DAG",
            input_requirements=[
                RoleRequirement("goal", "Goal to achieve", required=True),
                RoleRequirement("constraints", "Execution constraints", required=False)
            ],
            output_requirements=[
                RoleRequirement("plan", "Execution plan", required=True),
                RoleRequirement("dag", "Execution DAG", required=True)
            ],
            permissions=[
                RolePermission("create_dag", "system", "write", "limited"),
                RolePermission("invoke_planner", "tool", "execute", "specific", {"tools": ["planner"]})
            ],
            priority=8,
            learning_signals_consumed=["planner_genome_update"],
            learning_signals_produced=["plan_efficiency", "dag_complexity"]
        ))
        
        # Coordinator Role
        self.register(RoleSpec(
            role_id="coordinator",
            role_name="Coordinator",
            description="Coordinates multi-agent execution",
            input_requirements=[
                RoleRequirement("plan", "Execution plan", required=True),
                RoleRequirement("agents", "Available agents", required=True)
            ],
            output_requirements=[
                RoleRequirement("assignments", "Agent assignments", required=True),
                RoleRequirement("schedule", "Execution schedule", required=True)
            ],
            permissions=[
                RolePermission("invoke_agents", "agent", "invoke", "all"),
                RolePermission("coordinate", "system", "execute", "limited")
            ],
            priority=9,
            learning_signals_consumed=["coordination_policy_update"],
            learning_signals_produced=["coordination_efficiency", "parallelism_score"]
        ))
    
    def register(self, role: RoleSpec) -> None:
        """Register a role specification."""
        self._roles[role.role_id] = role
        self._save_role(role)
    
    def get(self, role_id: str) -> Optional[RoleSpec]:
        """Get role by ID."""
        return self._roles.get(role_id)
    
    def list_all(self) -> List[RoleSpec]:
        """List all roles."""
        return list(self._roles.values())
    
    def assign_role(
        self,
        run_id: str,
        role_id: str,
        agent_id: str,
        task_type: str,
        context: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None
    ) -> RoleAssignment:
        """
        Assign a role to an agent for a specific run.
        
        Args:
            run_id: Run identifier
            role_id: Role to assign
            agent_id: Agent to assign role to
            task_type: Type of task
            context: Assignment context
            overrides: Override role defaults
            
        Returns:
            RoleAssignment
        """
        overrides = overrides or {}
        
        assignment = RoleAssignment(
            assignment_id=f"assign_{run_id}_{role_id}_{agent_id}",
            run_id=run_id,
            role_id=role_id,
            agent_id=agent_id,
            task_type=task_type,
            context=context or {},
            override_max_retries=overrides.get("max_retries"),
            override_timeout_ms=overrides.get("timeout_ms"),
            override_priority=overrides.get("priority")
        )
        
        self._save_assignment(assignment)
        return assignment
    
    def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
        outcome: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update assignment status."""
        # Load, update, save
        path = os.path.join(self.assignments_dir, f"{assignment_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            data["status"] = status
            if outcome:
                data["outcome"] = outcome
            if status in ["completed", "failed"]:
                data["completed_at"] = datetime.now().isoformat()
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_assignments_for_run(self, run_id: str) -> List[RoleAssignment]:
        """Get all assignments for a run."""
        assignments = []
        
        # Save to run-specific file
        run_path = os.path.join(self.assignments_dir, f"{run_id}.json")
        if os.path.exists(run_path):
            with open(run_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for a_data in data.get("assignments", []):
                assignments.append(RoleAssignment(**a_data))
        
        return assignments
    
    def _save_role(self, role: RoleSpec) -> None:
        """Save role to artifact."""
        path = os.path.join(self.roles_dir, f"{role.role_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(role.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _save_assignment(self, assignment: RoleAssignment) -> None:
        """Save assignment to artifact."""
        # Save to run-specific file
        run_path = os.path.join(self.assignments_dir, f"{assignment.run_id}.json")
        
        # Load existing or create new
        if os.path.exists(run_path):
            with open(run_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "run_id": assignment.run_id,
                "schema_version": "1.0",
                "assignments": []
            }
        
        # Add assignment
        data["assignments"].append(assignment.to_dict())
        data["updated_at"] = datetime.now().isoformat()
        
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)



