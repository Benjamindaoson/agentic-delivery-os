"""
Agent Registry: First-class, auditable, evolvable agent definitions.
L5-grade: All agents are explicit entities with contracts and capabilities.
"""
import os
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class AgentCapability(str, Enum):
    """Standard agent capabilities (verbs)."""
    ANALYZE = "analyze"
    RETRIEVE = "retrieve"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    GENERATE = "generate"
    PLAN = "plan"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    ORCHESTRATE = "orchestrate"
    DECIDE = "decide"
    SUMMARIZE = "summarize"


@dataclass
class InputContract:
    """Agent input contract."""
    required_fields: List[str]
    optional_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, str] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutputContract:
    """Agent output contract."""
    guaranteed_fields: List[str]
    optional_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, str] = field(default_factory=dict)
    success_conditions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureMode:
    """Agent failure mode."""
    mode_id: str
    description: str
    severity: str  # low, medium, high, critical
    recovery_strategy: str
    attribution_layer: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentDefinition:
    """Complete agent definition."""
    agent_id: str
    role_name: str
    description: str
    capabilities: List[AgentCapability]
    allowed_tools: List[str]
    input_contract: InputContract
    output_contract: OutputContract
    failure_modes: List[FailureMode]
    version: str = "1.0"
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role_name": self.role_name,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "allowed_tools": self.allowed_tools,
            "input_contract": self.input_contract.to_dict(),
            "output_contract": self.output_contract.to_dict(),
            "failure_modes": [m.to_dict() for m in self.failure_modes],
            "version": self.version,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


class AgentRegistry:
    """
    Registry of all agent definitions.
    
    Provides:
    - Agent lookup by ID or role
    - Capability-based filtering
    - Snapshot export for audit
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.agents_dir = os.path.join(artifacts_dir, "agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        
        self._agents: Dict[str, AgentDefinition] = {}
        self._register_default_agents()
    
    def _register_default_agents(self) -> None:
        """Register default system agents."""
        # Product Agent
        self.register(AgentDefinition(
            agent_id="product_agent",
            role_name="Product",
            description="Interprets user requirements and validates delivery scope",
            capabilities=[AgentCapability.ANALYZE, AgentCapability.VALIDATE, AgentCapability.DECIDE],
            allowed_tools=["document_parser", "schema_validator"],
            input_contract=InputContract(
                required_fields=["user_request"],
                optional_fields=["context", "constraints"],
                field_types={"user_request": "string", "context": "object"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["spec_validated", "delivery_scope"],
                optional_fields=["clarification_needed"],
                field_types={"spec_validated": "boolean", "delivery_scope": "object"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="ambiguous_spec",
                    description="User specification is ambiguous",
                    severity="medium",
                    recovery_strategy="request_clarification",
                    attribution_layer="goal"
                )
            ]
        ))
        
        # Data Agent
        self.register(AgentDefinition(
            agent_id="data_agent",
            role_name="Data",
            description="Handles data retrieval, validation, and transformation",
            capabilities=[AgentCapability.RETRIEVE, AgentCapability.TRANSFORM, AgentCapability.VALIDATE],
            allowed_tools=["retriever", "embedder", "parser", "chunker"],
            input_contract=InputContract(
                required_fields=["query", "sources"],
                optional_fields=["filters", "max_results"],
                field_types={"query": "string", "sources": "array"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["documents", "retrieval_count"],
                optional_fields=["quality_score"],
                field_types={"documents": "array", "retrieval_count": "integer"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="retrieval_empty",
                    description="No documents retrieved",
                    severity="high",
                    recovery_strategy="expand_query",
                    attribution_layer="retrieval"
                ),
                FailureMode(
                    mode_id="retrieval_conflict",
                    description="Retrieved documents have conflicting information",
                    severity="medium",
                    recovery_strategy="request_human_review",
                    attribution_layer="retrieval"
                )
            ]
        ))
        
        # Execution Agent
        self.register(AgentDefinition(
            agent_id="execution_agent",
            role_name="Execution",
            description="Executes planned tasks and manages tool invocations",
            capabilities=[AgentCapability.EXECUTE, AgentCapability.ORCHESTRATE],
            allowed_tools=["*"],  # All tools
            input_contract=InputContract(
                required_fields=["execution_plan", "context"],
                optional_fields=["constraints"],
                field_types={"execution_plan": "object", "context": "object"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["execution_result", "status"],
                optional_fields=["artifacts_produced"],
                field_types={"execution_result": "object", "status": "string"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="tool_failure",
                    description="Tool invocation failed",
                    severity="high",
                    recovery_strategy="retry_with_fallback",
                    attribution_layer="tool"
                ),
                FailureMode(
                    mode_id="timeout",
                    description="Execution timeout",
                    severity="high",
                    recovery_strategy="abort_and_report",
                    attribution_layer="tool"
                )
            ]
        ))
        
        # Evaluation Agent
        self.register(AgentDefinition(
            agent_id="evaluation_agent",
            role_name="Evaluation",
            description="Evaluates outputs against success criteria",
            capabilities=[AgentCapability.EVALUATE, AgentCapability.VALIDATE],
            allowed_tools=["validator", "scorer", "diff_tool"],
            input_contract=InputContract(
                required_fields=["output", "criteria"],
                optional_fields=["baseline"],
                field_types={"output": "any", "criteria": "array"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["score", "passed", "details"],
                optional_fields=["recommendations"],
                field_types={"score": "number", "passed": "boolean"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="criteria_mismatch",
                    description="Output does not meet criteria",
                    severity="medium",
                    recovery_strategy="report_gaps",
                    attribution_layer="generation"
                )
            ]
        ))
        
        # Cost Agent
        self.register(AgentDefinition(
            agent_id="cost_agent",
            role_name="Cost",
            description="Monitors and controls execution costs",
            capabilities=[AgentCapability.ANALYZE, AgentCapability.DECIDE],
            allowed_tools=["cost_calculator", "budget_tracker"],
            input_contract=InputContract(
                required_fields=["budget", "current_spend"],
                optional_fields=["projections"],
                field_types={"budget": "number", "current_spend": "number"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["within_budget", "remaining"],
                optional_fields=["recommendations"],
                field_types={"within_budget": "boolean", "remaining": "number"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="budget_exceeded",
                    description="Budget limit exceeded",
                    severity="critical",
                    recovery_strategy="halt_execution",
                    attribution_layer="cost"
                )
            ]
        ))
        
        # Orchestrator Agent
        self.register(AgentDefinition(
            agent_id="orchestrator_agent",
            role_name="Orchestrator",
            description="Coordinates multi-agent workflows",
            capabilities=[AgentCapability.PLAN, AgentCapability.ORCHESTRATE, AgentCapability.DECIDE],
            allowed_tools=["planner", "scheduler", "coordinator"],
            input_contract=InputContract(
                required_fields=["goal", "available_agents"],
                optional_fields=["constraints", "priority"],
                field_types={"goal": "object", "available_agents": "array"}
            ),
            output_contract=OutputContract(
                guaranteed_fields=["execution_plan", "agent_assignments"],
                optional_fields=["contingencies"],
                field_types={"execution_plan": "object", "agent_assignments": "object"}
            ),
            failure_modes=[
                FailureMode(
                    mode_id="coordination_failure",
                    description="Agent coordination failed",
                    severity="high",
                    recovery_strategy="sequential_fallback",
                    attribution_layer="planner"
                )
            ]
        ))
    
    def register(self, agent: AgentDefinition) -> None:
        """Register an agent definition."""
        self._agents[agent.agent_id] = agent
    
    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def get_by_role(self, role_name: str) -> Optional[AgentDefinition]:
        """Get agent by role name."""
        for agent in self._agents.values():
            if agent.role_name.lower() == role_name.lower():
                return agent
        return None
    
    def get_by_capability(self, capability: AgentCapability) -> List[AgentDefinition]:
        """Get agents with a specific capability."""
        return [
            agent for agent in self._agents.values()
            if capability in agent.capabilities and agent.enabled
        ]
    
    def list_all(self) -> List[AgentDefinition]:
        """List all registered agents."""
        return list(self._agents.values())
    
    def export_snapshot(self) -> Dict[str, Any]:
        """Export registry snapshot for audit."""
        snapshot = {
            "schema_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "agent_count": len(self._agents),
            "agents": {
                agent_id: agent.to_dict()
                for agent_id, agent in self._agents.items()
            }
        }
        
        # Save to artifact
        path = os.path.join(self.agents_dir, "registry_snapshot.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        
        return snapshot
    
    def get_failure_modes_for_layer(self, layer: str) -> List[Dict[str, Any]]:
        """Get all failure modes attributed to a specific layer."""
        modes = []
        for agent in self._agents.values():
            for mode in agent.failure_modes:
                if mode.attribution_layer == layer:
                    modes.append({
                        "agent_id": agent.agent_id,
                        "mode": mode.to_dict()
                    })
        return modes



