"""
Agent Protocol: Protocol-based Agent Interface
P2-1 Implementation: Explicit input/output schemas, side-effect declarations, capability manifests

This module provides:
1. Protocol-based interface definition using ABC and typing.Protocol
2. Explicit input/output schemas with Pydantic
3. Side-effect declarations (artifacts, cost, state changes)
4. Capability manifests for agent discovery
5. Automatic compliance validation
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set, TypeVar, Generic, Protocol, runtime_checkable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import json
import hashlib

from pydantic import BaseModel, Field, validator


# ============================================================================
# Side Effect Declarations
# ============================================================================

class SideEffectType(str, Enum):
    """Types of side effects an agent can produce"""
    ARTIFACT_CREATE = "artifact_create"
    ARTIFACT_MODIFY = "artifact_modify"
    ARTIFACT_DELETE = "artifact_delete"
    STATE_UPDATE = "state_update"
    COST_INCUR = "cost_incur"
    EXTERNAL_CALL = "external_call"
    LLM_CALL = "llm_call"
    TOOL_INVOKE = "tool_invoke"


@dataclass
class SideEffectDeclaration:
    """Declaration of a side effect an agent may produce"""
    effect_type: SideEffectType
    description: str
    target: Optional[str] = None  # e.g., artifact path, state key
    estimated_cost: Optional[float] = None
    reversible: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect_type": self.effect_type.value,
            "description": self.description,
            "target": self.target,
            "estimated_cost": self.estimated_cost,
            "reversible": self.reversible
        }


# ============================================================================
# Capability Manifests
# ============================================================================

class CapabilityCategory(str, Enum):
    """Categories of agent capabilities"""
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    EVALUATION = "evaluation"
    COST_MANAGEMENT = "cost_management"
    DATA_HANDLING = "data_handling"
    ORCHESTRATION = "orchestration"


@dataclass
class Capability:
    """A single capability of an agent"""
    capability_id: str
    category: CapabilityCategory
    name: str
    description: str
    requires_llm: bool = False
    requires_tools: bool = False
    estimated_latency_ms: int = 1000
    estimated_cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "requires_llm": self.requires_llm,
            "requires_tools": self.requires_tools,
            "estimated_latency_ms": self.estimated_latency_ms,
            "estimated_cost": self.estimated_cost
        }


@dataclass
class AgentCapabilityManifest:
    """Complete capability manifest for an agent"""
    agent_id: str
    agent_name: str
    version: str
    description: str
    
    # Capabilities
    capabilities: List[Capability] = field(default_factory=list)
    
    # Side effects
    declared_side_effects: List[SideEffectDeclaration] = field(default_factory=list)
    
    # Resource requirements
    requires_llm: bool = False
    requires_tools: List[str] = field(default_factory=list)
    requires_external_access: bool = False
    
    # Constraints
    max_concurrent_executions: int = 10
    max_cost_per_execution: float = 1.0
    max_latency_ms: int = 30000
    
    # Metadata
    schema_version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "version": self.version,
            "description": self.description,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "declared_side_effects": [s.to_dict() for s in self.declared_side_effects],
            "requires_llm": self.requires_llm,
            "requires_tools": self.requires_tools,
            "requires_external_access": self.requires_external_access,
            "max_concurrent_executions": self.max_concurrent_executions,
            "max_cost_per_execution": self.max_cost_per_execution,
            "max_latency_ms": self.max_latency_ms,
            "schema_version": self.schema_version,
            "created_at": self.created_at
        }


# ============================================================================
# Input/Output Schemas
# ============================================================================

class AgentInput(BaseModel):
    """Base schema for agent input"""
    task_id: str = Field(..., description="Unique task identifier")
    run_id: Optional[str] = Field(None, description="Run identifier for tracing")
    
    # Context
    query: Optional[str] = Field(None, description="User query or goal")
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")
    
    # Constraints
    max_cost: Optional[float] = Field(None, description="Maximum allowed cost")
    max_latency_ms: Optional[int] = Field(None, description="Maximum allowed latency")
    
    # Metadata
    trace_enabled: bool = Field(True, description="Enable execution tracing")
    
    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class AgentOutput(BaseModel):
    """Base schema for agent output"""
    task_id: str = Field(..., description="Task identifier (echoed from input)")
    agent_name: str = Field(..., description="Name of the agent that produced this output")
    
    # Decision
    decision: str = Field(..., description="Agent's decision (proceed, terminate, etc.)")
    reason: Optional[str] = Field(None, description="Reason for the decision")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in decision")
    
    # Results
    result: Dict[str, Any] = Field(default_factory=dict, description="Agent-specific results")
    
    # State updates
    state_update: Dict[str, Any] = Field(default_factory=dict, description="State updates to apply")
    
    # Side effects produced
    side_effects_produced: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Actual side effects produced during execution"
    )
    
    # Cost tracking
    actual_cost: float = Field(0.0, ge=0.0, description="Actual cost incurred")
    actual_latency_ms: int = Field(0, ge=0, description="Actual execution time")
    
    # LLM usage (if any)
    llm_result: Optional[Dict[str, Any]] = Field(None, description="LLM call details if used")
    
    # Tool usage (if any)
    tool_executions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Tool execution details"
    )
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        extra = "allow"


# ============================================================================
# Protocol Definition
# ============================================================================

@runtime_checkable
class AgentProtocol(Protocol):
    """
    Protocol for all agents in the system.
    
    This defines the minimal interface that all agents must implement.
    Using typing.Protocol enables structural subtyping (duck typing).
    """
    
    @property
    def agent_name(self) -> str:
        """Return the agent's name"""
        ...
    
    @property
    def manifest(self) -> AgentCapabilityManifest:
        """Return the agent's capability manifest"""
        ...
    
    def get_input_schema(self) -> type:
        """Return the Pydantic model class for input validation"""
        ...
    
    def get_output_schema(self) -> type:
        """Return the Pydantic model class for output validation"""
        ...
    
    async def execute(
        self,
        input_data: AgentInput,
        task_id: str
    ) -> AgentOutput:
        """Execute the agent's main logic"""
        ...
    
    def get_governing_question(self) -> str:
        """Return the governance question this agent addresses"""
        ...


# ============================================================================
# Abstract Base Class Implementation
# ============================================================================

class ProtocolAgent(ABC):
    """
    Abstract base class for protocol-compliant agents.
    
    All agents should inherit from this class to ensure protocol compliance.
    """
    
    def __init__(
        self,
        agent_name: str,
        version: str = "1.0",
        description: str = ""
    ):
        self._agent_name = agent_name
        self._version = version
        self._description = description
        self._manifest: Optional[AgentCapabilityManifest] = None
    
    @property
    def agent_name(self) -> str:
        return self._agent_name
    
    @property
    def manifest(self) -> AgentCapabilityManifest:
        """Return the capability manifest, building it if needed"""
        if self._manifest is None:
            self._manifest = self._build_manifest()
        return self._manifest
    
    @abstractmethod
    def _build_manifest(self) -> AgentCapabilityManifest:
        """Build the capability manifest for this agent"""
        pass
    
    def get_input_schema(self) -> type:
        """Return input schema - can be overridden for custom schemas"""
        return AgentInput
    
    def get_output_schema(self) -> type:
        """Return output schema - can be overridden for custom schemas"""
        return AgentOutput
    
    @abstractmethod
    async def execute(
        self,
        input_data: AgentInput,
        task_id: str
    ) -> AgentOutput:
        """Execute agent logic - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def get_governing_question(self) -> str:
        """Return the governance question - must be implemented"""
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> AgentInput:
        """Validate and parse input data"""
        schema_class = self.get_input_schema()
        return schema_class(**input_data)
    
    def validate_output(self, output_data: Dict[str, Any]) -> AgentOutput:
        """Validate output data"""
        schema_class = self.get_output_schema()
        return schema_class(**output_data)
    
    async def safe_execute(
        self,
        context: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """
        Safe execution wrapper with validation.
        
        This method:
        1. Validates input against schema
        2. Executes agent logic
        3. Validates output against schema
        4. Tracks side effects
        5. Returns serializable result
        """
        start_time = datetime.now()
        
        # Build input
        input_data = self.validate_input({
            "task_id": task_id,
            "context": context,
            "query": context.get("query"),
            "max_cost": context.get("max_cost"),
            "max_latency_ms": context.get("max_latency_ms")
        })
        
        try:
            # Execute
            output = await self.execute(input_data, task_id)
            
            # Calculate latency
            end_time = datetime.now()
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            output.actual_latency_ms = latency_ms
            
            # Validate output
            validated_output = self.validate_output(output.model_dump())
            
            return validated_output.model_dump()
            
        except Exception as e:
            # Return error output
            return AgentOutput(
                task_id=task_id,
                agent_name=self.agent_name,
                decision="error",
                reason=str(e),
                confidence=0.0,
                actual_latency_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            ).model_dump()


# ============================================================================
# Compliance Checker
# ============================================================================

class AgentComplianceChecker:
    """
    Validates that agents comply with the protocol.
    
    Checks:
    1. Required methods exist
    2. Input/output schemas are valid
    3. Manifest is complete
    4. Side effects are declared
    """
    
    @staticmethod
    def check_protocol_compliance(agent: Any) -> Dict[str, Any]:
        """Check if an agent complies with the protocol"""
        issues = []
        warnings = []
        
        # Check required properties
        if not hasattr(agent, 'agent_name'):
            issues.append("Missing 'agent_name' property")
        
        if not hasattr(agent, 'manifest'):
            issues.append("Missing 'manifest' property")
        else:
            manifest = agent.manifest
            if not isinstance(manifest, AgentCapabilityManifest):
                issues.append("'manifest' is not an AgentCapabilityManifest instance")
            else:
                if not manifest.capabilities:
                    warnings.append("Manifest has no declared capabilities")
                if not manifest.declared_side_effects:
                    warnings.append("Manifest has no declared side effects")
        
        # Check required methods
        if not hasattr(agent, 'execute') or not callable(agent.execute):
            issues.append("Missing 'execute' method")
        
        if not hasattr(agent, 'get_governing_question') or not callable(agent.get_governing_question):
            issues.append("Missing 'get_governing_question' method")
        
        # Check schema methods
        if not hasattr(agent, 'get_input_schema') or not callable(agent.get_input_schema):
            warnings.append("Missing 'get_input_schema' method, using default")
        
        if not hasattr(agent, 'get_output_schema') or not callable(agent.get_output_schema):
            warnings.append("Missing 'get_output_schema' method, using default")
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "agent_name": getattr(agent, 'agent_name', 'unknown'),
            "checked_at": datetime.now().isoformat()
        }
    
    @staticmethod
    def validate_manifest(manifest: AgentCapabilityManifest) -> Dict[str, Any]:
        """Validate a capability manifest"""
        issues = []
        warnings = []
        
        if not manifest.agent_id:
            issues.append("Missing agent_id")
        
        if not manifest.agent_name:
            issues.append("Missing agent_name")
        
        if not manifest.version:
            warnings.append("Missing version")
        
        if not manifest.capabilities:
            warnings.append("No capabilities declared")
        
        # Check capability consistency
        for cap in manifest.capabilities:
            if cap.requires_llm and not manifest.requires_llm:
                issues.append(f"Capability '{cap.capability_id}' requires LLM but manifest doesn't declare LLM requirement")
        
        # Check side effect declarations
        for effect in manifest.declared_side_effects:
            if effect.effect_type == SideEffectType.COST_INCUR and effect.estimated_cost is None:
                warnings.append(f"Side effect declares cost impact but no estimate provided")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }


# ============================================================================
# Agent Registry Integration
# ============================================================================

class ProtocolAgentRegistry:
    """Registry for protocol-compliant agents"""
    
    def __init__(self):
        self.agents: Dict[str, ProtocolAgent] = {}
        self.manifests: Dict[str, AgentCapabilityManifest] = {}
        self.compliance_reports: Dict[str, Dict[str, Any]] = {}
    
    def register(self, agent: ProtocolAgent) -> bool:
        """Register an agent after compliance check"""
        compliance = AgentComplianceChecker.check_protocol_compliance(agent)
        self.compliance_reports[agent.agent_name] = compliance
        
        if not compliance["compliant"]:
            return False
        
        self.agents[agent.agent_name] = agent
        self.manifests[agent.agent_name] = agent.manifest
        return True
    
    def get_agent(self, agent_name: str) -> Optional[ProtocolAgent]:
        """Get a registered agent by name"""
        return self.agents.get(agent_name)
    
    def get_manifest(self, agent_name: str) -> Optional[AgentCapabilityManifest]:
        """Get agent manifest by name"""
        return self.manifests.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names"""
        return list(self.agents.keys())
    
    def find_by_capability(self, category: CapabilityCategory) -> List[str]:
        """Find agents by capability category"""
        result = []
        for name, manifest in self.manifests.items():
            for cap in manifest.capabilities:
                if cap.category == category:
                    result.append(name)
                    break
        return result
    
    def get_all_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Get all manifests as dictionaries"""
        return {name: manifest.to_dict() for name, manifest in self.manifests.items()}


# Global registry
_protocol_registry: Optional[ProtocolAgentRegistry] = None

def get_protocol_registry() -> ProtocolAgentRegistry:
    """Get global protocol agent registry"""
    global _protocol_registry
    if _protocol_registry is None:
        _protocol_registry = ProtocolAgentRegistry()
    return _protocol_registry


