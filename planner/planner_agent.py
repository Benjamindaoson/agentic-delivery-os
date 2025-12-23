"""
Planner Agent - Generates structured execution DAG from Goal Object
L5 Core Component: Dynamic Planning (not selection, but generation)
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import json
import os
import uuid


class PlanNode(BaseModel):
    """Single node in execution DAG"""
    node_id: str
    node_type: str  # retrieval | reasoning | generation | validation | tool_call
    description: str
    agent_role: str  # data_agent | reasoning_agent | execution_agent
    tool_requirements: List[str]
    input_requirements: List[str]
    expected_output: str
    estimated_cost: float
    estimated_latency_ms: int
    parallelizable: bool = False
    fallback_strategy: Optional[str] = None


class PlanEdge(BaseModel):
    """Edge representing dependency in DAG"""
    from_node: str
    to_node: str
    edge_type: str  # data_flow | control_flow | fallback
    condition: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Complete execution plan as DAG"""
    plan_id: str
    goal_id: str
    nodes: List[PlanNode]
    edges: List[PlanEdge]
    entry_points: List[str]  # Nodes with no dependencies
    exit_points: List[str]   # Nodes with no dependents
    parallelizable: bool
    fallback_paths: List[List[str]]  # Alternative execution paths
    total_estimated_cost: float
    total_estimated_latency_ms: int
    risk_mitigation: Dict[str, str]
    created_at: datetime = Field(default_factory=datetime.now)


class ConstraintManager:
    """Manages and enforces execution constraints"""
    
    def __init__(self):
        self.violation_log = []
    
    def validate_plan(self, plan: ExecutionPlan, constraints: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate plan against constraints
        Returns: (is_valid, list_of_violations)
        """
        violations = []
        
        # Check cost constraint
        max_cost = constraints.get("max_cost", float('inf'))
        if plan.total_estimated_cost > max_cost:
            violations.append(f"Cost {plan.total_estimated_cost} exceeds limit {max_cost}")
        
        # Check latency constraint
        max_latency = constraints.get("max_latency_ms", float('inf'))
        if plan.total_estimated_latency_ms > max_latency:
            violations.append(f"Latency {plan.total_estimated_latency_ms}ms exceeds limit {max_latency}ms")
        
        # Check safety level
        required_safety = constraints.get("safety_level", "standard")
        if required_safety == "high":
            # Ensure validation nodes exist
            has_validation = any(n.node_type == "validation" for n in plan.nodes)
            if not has_validation:
                violations.append("High safety mode requires validation nodes")
        
        # Check external API usage
        if not constraints.get("allow_external_api", False):
            for node in plan.nodes:
                if "external_api" in node.tool_requirements:
                    violations.append(f"Node {node.node_id} requires external API but not allowed")
        
        self.violation_log.extend(violations)
        return (len(violations) == 0, violations)
    
    def adjust_plan_for_constraints(self, plan: ExecutionPlan, constraints: Dict[str, Any]) -> ExecutionPlan:
        """Adjust plan to meet constraints if possible"""
        # Simple cost reduction: remove non-essential nodes
        if plan.total_estimated_cost > constraints.get("max_cost", float('inf')):
            # Keep only essential nodes (this is simplified logic)
            essential_nodes = [n for n in plan.nodes if n.node_type != "validation"]
            plan.nodes = essential_nodes
            plan.total_estimated_cost = sum(n.estimated_cost for n in plan.nodes)
        
        return plan


class PlannerAgent:
    """
    Core L5 Planner: Generates (not selects) execution plans from goals
    """
    
    def __init__(self, artifacts_path: str = "artifacts/plans"):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        self.constraint_manager = ConstraintManager()
        
        # Planning templates by goal type
        self.templates = {
            "retrieve": self._plan_retrieval,
            "analyze": self._plan_analysis,
            "build": self._plan_generation,
            "audit": self._plan_audit,
            "qa": self._plan_qa,
            "summarize": self._plan_summarization
        }
    
    def create_plan(self, goal: Any) -> ExecutionPlan:
        """
        Main planning method
        Args:
            goal: GoalObject from interpreter
        Returns:
            ExecutionPlan as structured DAG
        """
        # Select planning strategy based on goal type
        planner_func = self.templates.get(goal.goal_type, self._plan_default)
        
        # Generate initial plan
        nodes, edges = planner_func(goal)
        
        # Create plan object
        plan = self._assemble_plan(goal, nodes, edges)
        
        # Validate against constraints
        is_valid, violations = self.constraint_manager.validate_plan(plan, goal.constraints)
        
        if not is_valid:
            # Attempt adjustment
            plan = self.constraint_manager.adjust_plan_for_constraints(plan, goal.constraints)
            
            # Re-validate
            is_valid, violations = self.constraint_manager.validate_plan(plan, goal.constraints)
            
            if not is_valid:
                # Log violations but proceed (can fail later)
                print(f"⚠️ Plan has constraint violations: {violations}")
        
        # Add fallback paths
        plan.fallback_paths = self._generate_fallback_paths(plan)
        
        # Persist plan
        self._save_plan(plan)
        
        return plan
    
    def _plan_retrieval(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for retrieval goals"""
        nodes = [
            PlanNode(
                node_id="retrieve_1",
                node_type="retrieval",
                description="Retrieve relevant documents",
                agent_role="data_agent",
                tool_requirements=["retriever", "reranker"],
                input_requirements=["query"],
                expected_output="document_list",
                estimated_cost=0.01,
                estimated_latency_ms=500,
                parallelizable=False
            ),
            PlanNode(
                node_id="synthesize_1",
                node_type="generation",
                description="Synthesize answer from documents",
                agent_role="reasoning_agent",
                tool_requirements=["llm_generator"],
                input_requirements=["document_list", "query"],
                expected_output="final_answer",
                estimated_cost=0.02,
                estimated_latency_ms=1000,
                parallelizable=False
            ),
            PlanNode(
                node_id="validate_1",
                node_type="validation",
                description="Validate answer groundedness",
                agent_role="execution_agent",
                tool_requirements=["evidence_validator"],
                input_requirements=["final_answer", "document_list"],
                expected_output="validation_result",
                estimated_cost=0.005,
                estimated_latency_ms=200,
                parallelizable=False
            )
        ]
        
        edges = [
            PlanEdge(from_node="retrieve_1", to_node="synthesize_1", edge_type="data_flow"),
            PlanEdge(from_node="synthesize_1", to_node="validate_1", edge_type="control_flow")
        ]
        
        return nodes, edges
    
    def _plan_analysis(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for analysis goals"""
        nodes = [
            PlanNode(
                node_id="retrieve_all",
                node_type="retrieval",
                description="Retrieve all relevant items",
                agent_role="data_agent",
                tool_requirements=["retriever"],
                input_requirements=["query"],
                expected_output="item_list",
                estimated_cost=0.015,
                estimated_latency_ms=800,
                parallelizable=False
            ),
            PlanNode(
                node_id="compare",
                node_type="reasoning",
                description="Perform comparison analysis",
                agent_role="reasoning_agent",
                tool_requirements=["comparator", "llm_generator"],
                input_requirements=["item_list"],
                expected_output="comparison_result",
                estimated_cost=0.03,
                estimated_latency_ms=1500,
                parallelizable=False
            ),
            PlanNode(
                node_id="summarize",
                node_type="generation",
                description="Summarize findings",
                agent_role="reasoning_agent",
                tool_requirements=["summarizer"],
                input_requirements=["comparison_result"],
                expected_output="summary",
                estimated_cost=0.01,
                estimated_latency_ms=500,
                parallelizable=False
            )
        ]
        
        edges = [
            PlanEdge(from_node="retrieve_all", to_node="compare", edge_type="data_flow"),
            PlanEdge(from_node="compare", to_node="summarize", edge_type="data_flow")
        ]
        
        return nodes, edges
    
    def _plan_generation(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for generation/build goals"""
        nodes = [
            PlanNode(
                node_id="gather_specs",
                node_type="retrieval",
                description="Gather requirements and context",
                agent_role="data_agent",
                tool_requirements=["retriever"],
                input_requirements=["query"],
                expected_output="specifications",
                estimated_cost=0.01,
                estimated_latency_ms=500,
                parallelizable=False
            ),
            PlanNode(
                node_id="generate",
                node_type="generation",
                description="Generate output",
                agent_role="reasoning_agent",
                tool_requirements=["llm_generator"],
                input_requirements=["specifications"],
                expected_output="generated_output",
                estimated_cost=0.04,
                estimated_latency_ms=2000,
                parallelizable=False
            ),
            PlanNode(
                node_id="validate_output",
                node_type="validation",
                description="Validate generated output",
                agent_role="execution_agent",
                tool_requirements=["validator"],
                input_requirements=["generated_output", "specifications"],
                expected_output="validated_output",
                estimated_cost=0.01,
                estimated_latency_ms=400,
                parallelizable=False
            )
        ]
        
        edges = [
            PlanEdge(from_node="gather_specs", to_node="generate", edge_type="data_flow"),
            PlanEdge(from_node="generate", to_node="validate_output", edge_type="control_flow")
        ]
        
        return nodes, edges
    
    def _plan_audit(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for audit goals"""
        nodes = [
            PlanNode(
                node_id="retrieve_history",
                node_type="retrieval",
                description="Retrieve audit target history",
                agent_role="data_agent",
                tool_requirements=["retriever"],
                input_requirements=["target_id"],
                expected_output="history",
                estimated_cost=0.01,
                estimated_latency_ms=400,
                parallelizable=False
            ),
            PlanNode(
                node_id="check_compliance",
                node_type="validation",
                description="Check compliance rules",
                agent_role="execution_agent",
                tool_requirements=["rule_checker"],
                input_requirements=["history"],
                expected_output="compliance_report",
                estimated_cost=0.02,
                estimated_latency_ms=1000,
                parallelizable=False
            )
        ]
        
        edges = [
            PlanEdge(from_node="retrieve_history", to_node="check_compliance", edge_type="data_flow")
        ]
        
        return nodes, edges
    
    def _plan_qa(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for Q&A goals"""
        return self._plan_retrieval(goal)  # Similar to retrieval
    
    def _plan_summarization(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Plan for summarization goals"""
        nodes = [
            PlanNode(
                node_id="retrieve_content",
                node_type="retrieval",
                description="Retrieve content to summarize",
                agent_role="data_agent",
                tool_requirements=["retriever"],
                input_requirements=["query"],
                expected_output="content",
                estimated_cost=0.01,
                estimated_latency_ms=400,
                parallelizable=False
            ),
            PlanNode(
                node_id="summarize",
                node_type="generation",
                description="Generate summary",
                agent_role="reasoning_agent",
                tool_requirements=["summarizer"],
                input_requirements=["content"],
                expected_output="summary",
                estimated_cost=0.015,
                estimated_latency_ms=800,
                parallelizable=False
            )
        ]
        
        edges = [
            PlanEdge(from_node="retrieve_content", to_node="summarize", edge_type="data_flow")
        ]
        
        return nodes, edges
    
    def _plan_default(self, goal: Any) -> tuple[List[PlanNode], List[PlanEdge]]:
        """Default fallback plan"""
        return self._plan_retrieval(goal)
    
    def _assemble_plan(self, goal: Any, nodes: List[PlanNode], edges: List[PlanEdge]) -> ExecutionPlan:
        """Assemble plan from nodes and edges"""
        plan_id = f"plan_{uuid.uuid4().hex[:16]}"
        
        # Compute entry/exit points
        to_nodes = {e.to_node for e in edges}
        from_nodes = {e.from_node for e in edges}
        all_nodes = {n.node_id for n in nodes}
        
        entry_points = list(all_nodes - to_nodes)
        exit_points = list(all_nodes - from_nodes)
        
        # Check if parallelizable
        parallelizable = len(entry_points) > 1
        
        # Compute totals
        total_cost = sum(n.estimated_cost for n in nodes)
        total_latency = self._compute_critical_path_latency(nodes, edges)
        
        # Risk mitigation strategies
        risk_mitigation = {
            "high_cost": "Enable cost monitoring and early termination",
            "high_latency": "Implement timeout per node",
            "data_unavailable": "Use fallback data sources",
            "validation_failure": "Request human review"
        }
        
        return ExecutionPlan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            nodes=nodes,
            edges=edges,
            entry_points=entry_points,
            exit_points=exit_points,
            parallelizable=parallelizable,
            fallback_paths=[],  # Will be populated later
            total_estimated_cost=total_cost,
            total_estimated_latency_ms=total_latency,
            risk_mitigation=risk_mitigation
        )
    
    def _compute_critical_path_latency(self, nodes: List[PlanNode], edges: List[PlanEdge]) -> int:
        """Compute critical path latency (simplified: assume sequential)"""
        return sum(n.estimated_latency_ms for n in nodes)
    
    def _generate_fallback_paths(self, plan: ExecutionPlan) -> List[List[str]]:
        """Generate alternative execution paths for fault tolerance"""
        # Simplified: create one fallback that skips validation
        main_path = [n.node_id for n in plan.nodes]
        fallback = [n.node_id for n in plan.nodes if n.node_type != "validation"]
        
        if len(fallback) < len(main_path):
            return [fallback]
        return []
    
    def _save_plan(self, plan: ExecutionPlan):
        """Persist plan to artifacts"""
        path = os.path.join(self.artifacts_path, f"{plan.plan_id}.json")
        with open(path, "w") as f:
            f.write(plan.model_dump_json(indent=2))


# Singleton instance
_planner = None

def get_planner() -> PlannerAgent:
    """Get singleton PlannerAgent instance"""
    global _planner
    if _planner is None:
        _planner = PlannerAgent()
    return _planner



