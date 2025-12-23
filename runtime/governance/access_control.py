"""
Access Control: Agent, tool, and memory access governance.
Explicit permission model for system resources.
"""
import os
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class ResourceType(str, Enum):
    """Types of resources."""
    TOOL = "tool"
    AGENT = "agent"
    MEMORY = "memory"
    DATA = "data"
    API = "api"
    SYSTEM = "system"


class ActionType(str, Enum):
    """Types of actions."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Permission:
    """A single permission."""
    permission_id: str
    resource_type: ResourceType
    resource_id: str  # "*" for all
    action: ActionType
    granted: bool = True
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["resource_type"] = self.resource_type.value
        result["action"] = self.action.value
        return result


@dataclass
class Role:
    """A role with permissions."""
    role_id: str
    role_name: str
    description: str
    permissions: List[Permission]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions]
        }


@dataclass
class AccessDecision:
    """Result of an access check."""
    allowed: bool
    resource_type: ResourceType
    resource_id: str
    action: ActionType
    reason: str
    checked_at: str = ""
    
    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["resource_type"] = self.resource_type.value
        result["action"] = self.action.value
        return result


class AccessController:
    """
    Manages access control for system resources.
    
    Provides:
    - Role-based access control
    - Resource-level permissions
    - Audit logging
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.acl_dir = os.path.join(artifacts_dir, "governance", "acl")
        os.makedirs(self.acl_dir, exist_ok=True)
        
        self._roles: Dict[str, Role] = {}
        self._agent_roles: Dict[str, str] = {}  # agent_id -> role_id
        
        self._init_default_roles()
    
    def _init_default_roles(self) -> None:
        """Initialize default roles."""
        # Admin role
        self._roles["admin"] = Role(
            role_id="admin",
            role_name="Administrator",
            description="Full system access",
            permissions=[
                Permission("admin_all", ResourceType.SYSTEM, "*", ActionType.ADMIN)
            ]
        )
        
        # Orchestrator role
        self._roles["orchestrator"] = Role(
            role_id="orchestrator",
            role_name="Orchestrator",
            description="Can coordinate agents and tools",
            permissions=[
                Permission("orch_agent_exec", ResourceType.AGENT, "*", ActionType.EXECUTE),
                Permission("orch_tool_exec", ResourceType.TOOL, "*", ActionType.EXECUTE),
                Permission("orch_memory_read", ResourceType.MEMORY, "*", ActionType.READ),
                Permission("orch_memory_write", ResourceType.MEMORY, "*", ActionType.WRITE)
            ]
        )
        
        # Data agent role
        self._roles["data_agent"] = Role(
            role_id="data_agent",
            role_name="Data Agent",
            description="Can access data and retrieval tools",
            permissions=[
                Permission("data_read", ResourceType.DATA, "*", ActionType.READ),
                Permission("data_tool_exec", ResourceType.TOOL, "retriever", ActionType.EXECUTE),
                Permission("data_tool_embed", ResourceType.TOOL, "embedder", ActionType.EXECUTE)
            ]
        )
        
        # Execution agent role
        self._roles["execution_agent"] = Role(
            role_id="execution_agent",
            role_name="Execution Agent",
            description="Can execute approved tools",
            permissions=[
                Permission("exec_tool", ResourceType.TOOL, "*", ActionType.EXECUTE,
                          conditions={"approved_only": True}),
                Permission("exec_memory_read", ResourceType.MEMORY, "working", ActionType.READ)
            ]
        )
        
        # Read-only role
        self._roles["readonly"] = Role(
            role_id="readonly",
            role_name="Read Only",
            description="Can only read resources",
            permissions=[
                Permission("read_data", ResourceType.DATA, "*", ActionType.READ),
                Permission("read_memory", ResourceType.MEMORY, "*", ActionType.READ)
            ]
        )
        
        # Assign default roles
        self._agent_roles["orchestrator_agent"] = "orchestrator"
        self._agent_roles["data_agent"] = "data_agent"
        self._agent_roles["execution_agent"] = "execution_agent"
        self._agent_roles["evaluation_agent"] = "readonly"
    
    def check_access(
        self,
        agent_id: str,
        resource_type: ResourceType,
        resource_id: str,
        action: ActionType
    ) -> AccessDecision:
        """
        Check if an agent has access to a resource.
        
        Args:
            agent_id: The agent requesting access
            resource_type: Type of resource
            resource_id: ID of the resource
            action: Action being attempted
            
        Returns:
            AccessDecision
        """
        role_id = self._agent_roles.get(agent_id)
        
        if not role_id:
            return AccessDecision(
                allowed=False,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                reason=f"No role assigned to agent {agent_id}"
            )
        
        role = self._roles.get(role_id)
        
        if not role:
            return AccessDecision(
                allowed=False,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                reason=f"Role {role_id} not found"
            )
        
        # Check permissions
        for perm in role.permissions:
            if self._permission_matches(perm, resource_type, resource_id, action):
                if perm.granted:
                    decision = AccessDecision(
                        allowed=True,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=action,
                        reason=f"Granted by permission {perm.permission_id}"
                    )
                    self._log_access(agent_id, decision)
                    return decision
        
        decision = AccessDecision(
            allowed=False,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            reason=f"No matching permission in role {role_id}"
        )
        self._log_access(agent_id, decision)
        return decision
    
    def assign_role(self, agent_id: str, role_id: str) -> bool:
        """Assign a role to an agent."""
        if role_id not in self._roles:
            return False
        self._agent_roles[agent_id] = role_id
        return True
    
    def get_agent_permissions(self, agent_id: str) -> List[Permission]:
        """Get all permissions for an agent."""
        role_id = self._agent_roles.get(agent_id)
        if not role_id:
            return []
        
        role = self._roles.get(role_id)
        return role.permissions if role else []
    
    def create_role(self, role: Role) -> None:
        """Create a new role."""
        self._roles[role.role_id] = role
        self._save_roles()
    
    def _permission_matches(
        self,
        perm: Permission,
        resource_type: ResourceType,
        resource_id: str,
        action: ActionType
    ) -> bool:
        """Check if a permission matches a request."""
        # Admin permission matches everything
        if perm.action == ActionType.ADMIN and perm.resource_id == "*":
            return True
        
        # Check resource type
        if perm.resource_type != resource_type:
            return False
        
        # Check resource ID (wildcard or exact)
        if perm.resource_id != "*" and perm.resource_id != resource_id:
            return False
        
        # Check action
        if perm.action != action:
            return False
        
        return True
    
    def _log_access(self, agent_id: str, decision: AccessDecision) -> None:
        """Log an access decision."""
        log_path = os.path.join(self.acl_dir, "access_log.jsonl")
        
        log_entry = {
            "agent_id": agent_id,
            "decision": decision.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def _save_roles(self) -> None:
        """Save roles to file."""
        path = os.path.join(self.acl_dir, "roles.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {rid: r.to_dict() for rid, r in self._roles.items()},
                f, indent=2, ensure_ascii=False
            )
