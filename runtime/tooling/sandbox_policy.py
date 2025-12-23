"""
Sandbox Policy: Logical sandboxing for tool permissions and risk tiers.
L5-grade: Sandboxing is explicit, artifact-driven, no infra changes.
"""
import os
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class RiskTier(str, Enum):
    """Risk tiers for tools."""
    LOW = "low"  # Read-only, no external effects
    MEDIUM = "medium"  # Limited external effects
    HIGH = "high"  # Significant external effects
    CRITICAL = "critical"  # Irreversible or security-sensitive


class PermissionType(str, Enum):
    """Types of permissions."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    EXTERNAL_API = "external_api"


@dataclass
class ToolPermission:
    """Permission for a tool."""
    permission_id: str
    permission_type: PermissionType
    resource: str
    granted: bool
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["permission_type"] = self.permission_type.value
        return result


@dataclass
class ToolRiskAssessment:
    """Risk assessment for a tool."""
    tool_name: str
    risk_tier: RiskTier
    risk_score: float  # 0.0-1.0
    
    # Risk factors
    has_side_effects: bool
    is_reversible: bool
    accesses_external: bool
    handles_sensitive_data: bool
    
    # Mitigations
    required_approvals: List[str] = field(default_factory=list)
    audit_required: bool = True
    sandbox_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["risk_tier"] = self.risk_tier.value
        return result


@dataclass
class SandboxDecision:
    """Sandbox decision for a run."""
    decision_id: str
    run_id: str
    
    # Tools assessed
    tool_assessments: List[ToolRiskAssessment]
    
    # Permissions granted
    permissions_granted: List[ToolPermission]
    permissions_denied: List[ToolPermission]
    
    # Overall decision
    sandbox_mode: str  # none, soft, hard
    risk_level: str  # low, medium, high, critical
    
    # Constraints applied
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    decided_at: str = ""
    rationale: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.decided_at:
            self.decided_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "run_id": self.run_id,
            "tool_assessments": [a.to_dict() for a in self.tool_assessments],
            "permissions_granted": [p.to_dict() for p in self.permissions_granted],
            "permissions_denied": [p.to_dict() for p in self.permissions_denied],
            "sandbox_mode": self.sandbox_mode,
            "risk_level": self.risk_level,
            "constraints": self.constraints,
            "decided_at": self.decided_at,
            "rationale": self.rationale,
            "schema_version": self.schema_version
        }


class SandboxPolicy:
    """
    Logical sandboxing for tools.
    
    Provides:
    - Risk tier assignment per tool
    - Permission constraints
    - Sandbox decision artifacts
    
    No infrastructure changes - pure policy layer.
    """
    
    # Default risk assessments
    DEFAULT_ASSESSMENTS = {
        "document_parser": ToolRiskAssessment(
            tool_name="document_parser",
            risk_tier=RiskTier.LOW,
            risk_score=0.1,
            has_side_effects=False,
            is_reversible=True,
            accesses_external=False,
            handles_sensitive_data=False,
            audit_required=False
        ),
        "chunker": ToolRiskAssessment(
            tool_name="chunker",
            risk_tier=RiskTier.LOW,
            risk_score=0.1,
            has_side_effects=False,
            is_reversible=True,
            accesses_external=False,
            handles_sensitive_data=False,
            audit_required=False
        ),
        "embedder": ToolRiskAssessment(
            tool_name="embedder",
            risk_tier=RiskTier.LOW,
            risk_score=0.2,
            has_side_effects=False,
            is_reversible=True,
            accesses_external=True,  # May call embedding API
            handles_sensitive_data=True,
            audit_required=True
        ),
        "retriever": ToolRiskAssessment(
            tool_name="retriever",
            risk_tier=RiskTier.LOW,
            risk_score=0.2,
            has_side_effects=False,
            is_reversible=True,
            accesses_external=False,
            handles_sensitive_data=True,
            audit_required=True
        ),
        "llm_generator": ToolRiskAssessment(
            tool_name="llm_generator",
            risk_tier=RiskTier.MEDIUM,
            risk_score=0.4,
            has_side_effects=False,
            is_reversible=True,
            accesses_external=True,
            handles_sensitive_data=True,
            audit_required=True
        ),
        "file_writer": ToolRiskAssessment(
            tool_name="file_writer",
            risk_tier=RiskTier.HIGH,
            risk_score=0.7,
            has_side_effects=True,
            is_reversible=False,
            accesses_external=False,
            handles_sensitive_data=True,
            required_approvals=["user"],
            audit_required=True,
            sandbox_required=True
        ),
        "external_api_caller": ToolRiskAssessment(
            tool_name="external_api_caller",
            risk_tier=RiskTier.HIGH,
            risk_score=0.8,
            has_side_effects=True,
            is_reversible=False,
            accesses_external=True,
            handles_sensitive_data=True,
            required_approvals=["user", "security"],
            audit_required=True,
            sandbox_required=True
        ),
        "database_writer": ToolRiskAssessment(
            tool_name="database_writer",
            risk_tier=RiskTier.CRITICAL,
            risk_score=0.9,
            has_side_effects=True,
            is_reversible=False,
            accesses_external=True,
            handles_sensitive_data=True,
            required_approvals=["user", "security", "dba"],
            audit_required=True,
            sandbox_required=True
        )
    }
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.sandbox_dir = os.path.join(artifacts_dir, "tooling", "sandbox_decisions")
        os.makedirs(self.sandbox_dir, exist_ok=True)
        
        self._assessments = dict(self.DEFAULT_ASSESSMENTS)
    
    def assess_tool(self, tool_name: str) -> ToolRiskAssessment:
        """Get risk assessment for a tool."""
        if tool_name in self._assessments:
            return self._assessments[tool_name]
        
        # Default assessment for unknown tools
        return ToolRiskAssessment(
            tool_name=tool_name,
            risk_tier=RiskTier.MEDIUM,
            risk_score=0.5,
            has_side_effects=True,  # Assume worst case
            is_reversible=False,
            accesses_external=True,
            handles_sensitive_data=True,
            audit_required=True,
            sandbox_required=True
        )
    
    def register_assessment(self, assessment: ToolRiskAssessment) -> None:
        """Register a custom risk assessment."""
        self._assessments[assessment.tool_name] = assessment
    
    def evaluate_permissions(
        self,
        run_id: str,
        tools: List[str],
        requested_permissions: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> SandboxDecision:
        """
        Evaluate and decide on tool permissions for a run.
        
        Args:
            run_id: Run identifier
            tools: List of tools to be used
            requested_permissions: Explicitly requested permissions
            context: Run context for policy decisions
            
        Returns:
            SandboxDecision
        """
        context = context or {}
        
        # Assess all tools
        assessments = [self.assess_tool(tool) for tool in tools]
        
        # Determine overall risk level
        max_risk = max(a.risk_tier for a in assessments) if assessments else RiskTier.LOW
        avg_risk_score = sum(a.risk_score for a in assessments) / len(assessments) if assessments else 0.0
        
        # Determine sandbox mode
        if max_risk == RiskTier.CRITICAL:
            sandbox_mode = "hard"
        elif max_risk == RiskTier.HIGH:
            sandbox_mode = "soft"
        else:
            sandbox_mode = "none"
        
        # Evaluate permissions
        granted = []
        denied = []
        
        for assessment in assessments:
            tool = assessment.tool_name
            
            # Default permissions based on risk tier
            if assessment.risk_tier in [RiskTier.LOW, RiskTier.MEDIUM]:
                granted.append(ToolPermission(
                    permission_id=f"{tool}_read",
                    permission_type=PermissionType.READ,
                    resource="*",
                    granted=True
                ))
                granted.append(ToolPermission(
                    permission_id=f"{tool}_execute",
                    permission_type=PermissionType.EXECUTE,
                    resource=tool,
                    granted=True
                ))
            
            # High/critical tools need explicit approval
            if assessment.risk_tier in [RiskTier.HIGH, RiskTier.CRITICAL]:
                if context.get("approved_tools", []) and tool in context["approved_tools"]:
                    granted.append(ToolPermission(
                        permission_id=f"{tool}_execute",
                        permission_type=PermissionType.EXECUTE,
                        resource=tool,
                        granted=True,
                        conditions={"requires_audit": True}
                    ))
                else:
                    denied.append(ToolPermission(
                        permission_id=f"{tool}_execute",
                        permission_type=PermissionType.EXECUTE,
                        resource=tool,
                        granted=False,
                        conditions={"reason": "requires_approval"}
                    ))
            
            # Network permissions
            if assessment.accesses_external:
                if context.get("allow_network", True):
                    granted.append(ToolPermission(
                        permission_id=f"{tool}_network",
                        permission_type=PermissionType.NETWORK,
                        resource="external",
                        granted=True
                    ))
                else:
                    denied.append(ToolPermission(
                        permission_id=f"{tool}_network",
                        permission_type=PermissionType.NETWORK,
                        resource="external",
                        granted=False,
                        conditions={"reason": "network_disabled"}
                    ))
        
        # Build constraints
        constraints = {
            "max_execution_time_ms": 60000 if sandbox_mode == "hard" else 300000,
            "max_retries": 1 if sandbox_mode == "hard" else 3,
            "audit_all_calls": sandbox_mode in ["soft", "hard"],
            "dry_run_required": sandbox_mode == "hard"
        }
        
        decision = SandboxDecision(
            decision_id=f"sandbox_{run_id}",
            run_id=run_id,
            tool_assessments=assessments,
            permissions_granted=granted,
            permissions_denied=denied,
            sandbox_mode=sandbox_mode,
            risk_level=max_risk.value,
            constraints=constraints,
            rationale=f"Risk level {max_risk.value} based on {len(assessments)} tools, avg score {avg_risk_score:.2f}"
        )
        
        # Save artifact
        self._save_decision(decision)
        
        return decision
    
    def check_permission(
        self,
        decision: SandboxDecision,
        tool_name: str,
        permission_type: PermissionType
    ) -> bool:
        """Check if a specific permission is granted."""
        for perm in decision.permissions_granted:
            if perm.permission_type == permission_type:
                if perm.resource == "*" or perm.resource == tool_name:
                    return perm.granted
        
        return False
    
    def load_decision(self, run_id: str) -> Optional[SandboxDecision]:
        """Load sandbox decision for a run."""
        path = os.path.join(self.sandbox_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return self._dict_to_decision(data)
    
    def _save_decision(self, decision: SandboxDecision) -> None:
        """Save decision to artifact."""
        path = os.path.join(self.sandbox_dir, f"{decision.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_decision(self, data: Dict[str, Any]) -> SandboxDecision:
        """Convert dict to SandboxDecision."""
        return SandboxDecision(
            decision_id=data["decision_id"],
            run_id=data["run_id"],
            tool_assessments=[
                ToolRiskAssessment(
                    tool_name=a["tool_name"],
                    risk_tier=RiskTier(a["risk_tier"]),
                    risk_score=a["risk_score"],
                    has_side_effects=a["has_side_effects"],
                    is_reversible=a["is_reversible"],
                    accesses_external=a["accesses_external"],
                    handles_sensitive_data=a["handles_sensitive_data"],
                    required_approvals=a.get("required_approvals", []),
                    audit_required=a.get("audit_required", True),
                    sandbox_required=a.get("sandbox_required", False)
                )
                for a in data["tool_assessments"]
            ],
            permissions_granted=[
                ToolPermission(
                    permission_id=p["permission_id"],
                    permission_type=PermissionType(p["permission_type"]),
                    resource=p["resource"],
                    granted=p["granted"],
                    conditions=p.get("conditions", {})
                )
                for p in data["permissions_granted"]
            ],
            permissions_denied=[
                ToolPermission(
                    permission_id=p["permission_id"],
                    permission_type=PermissionType(p["permission_type"]),
                    resource=p["resource"],
                    granted=p["granted"],
                    conditions=p.get("conditions", {})
                )
                for p in data["permissions_denied"]
            ],
            sandbox_mode=data["sandbox_mode"],
            risk_level=data["risk_level"],
            constraints=data.get("constraints", {}),
            decided_at=data.get("decided_at", ""),
            rationale=data.get("rationale", ""),
            schema_version=data.get("schema_version", "1.0")
        )



