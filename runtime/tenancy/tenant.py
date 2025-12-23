"""
Tenant - Multi-tenant architecture core
L6 Component: Scale Layer - Multi-Tenancy
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os
import uuid


class BudgetProfile(BaseModel):
    """Tenant budget configuration"""
    max_cost_per_day: float
    max_cost_per_month: float
    max_concurrent_runs: int
    max_agents: int
    priority_level: int = 5  # 1-10
    cost_alerts_enabled: bool = True
    alert_threshold_pct: float = 0.8


class PolicySpace(BaseModel):
    """Tenant-specific policy space"""
    planner_policies: Dict[str, Any] = {}
    tool_policies: Dict[str, Any] = {}
    agent_policies: Dict[str, Any] = {}
    generation_policies: Dict[str, Any] = {}
    custom_policies: Dict[str, Any] = {}


class LearningState(BaseModel):
    """Tenant-specific learning state"""
    total_runs: int = 0
    successful_runs: int = 0
    policy_updates: int = 0
    last_update: Optional[datetime] = None
    learning_enabled: bool = True
    share_meta_learning: bool = False  # Opt-in for meta-learning


class Tenant(BaseModel):
    """
    Core tenant entity
    Represents a single tenant in multi-tenant system
    """
    tenant_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    
    # Configuration
    budget_profile: BudgetProfile
    policy_space: PolicySpace = Field(default_factory=PolicySpace)
    learning_state: LearningState = Field(default_factory=LearningState)
    
    # Projects under this tenant
    project_ids: List[str] = []
    
    # Isolation settings
    isolated_memory: bool = True
    isolated_learning: bool = True
    can_fork_policies: bool = True
    
    # Metadata
    tags: Dict[str, str] = {}
    metadata: Dict[str, Any] = {}


class TenantManager:
    """
    Manages tenant lifecycle and isolation
    """
    
    def __init__(self, storage_path: str = "artifacts/tenants"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
        # In-memory cache
        self.tenants: Dict[str, Tenant] = {}
        
        # Load existing tenants
        self._load_tenants()
    
    def create_tenant(
        self,
        name: str,
        budget_profile: BudgetProfile,
        tenant_id: Optional[str] = None
    ) -> Tenant:
        """Create a new tenant"""
        if tenant_id is None:
            tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        
        if tenant_id in self.tenants:
            raise ValueError(f"Tenant {tenant_id} already exists")
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            budget_profile=budget_profile
        )
        
        self.tenants[tenant_id] = tenant
        self._save_tenant(tenant)
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)
    
    def list_tenants(self, active_only: bool = True) -> List[Tenant]:
        """List all tenants"""
        tenants = list(self.tenants.values())
        if active_only:
            tenants = [t for t in tenants if t.is_active]
        return tenants
    
    def update_tenant(self, tenant: Tenant):
        """Update tenant configuration"""
        self.tenants[tenant.tenant_id] = tenant
        self._save_tenant(tenant)
    
    def deactivate_tenant(self, tenant_id: str):
        """Deactivate a tenant"""
        if tenant_id in self.tenants:
            tenant = self.tenants[tenant_id]
            tenant.is_active = False
            self._save_tenant(tenant)
    
    def add_project(self, tenant_id: str, project_id: str):
        """Add a project to tenant"""
        if tenant_id in self.tenants:
            tenant = self.tenants[tenant_id]
            if project_id not in tenant.project_ids:
                tenant.project_ids.append(project_id)
                self._save_tenant(tenant)
    
    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant resource usage"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        return {
            "tenant_id": tenant_id,
            "total_runs": tenant.learning_state.total_runs,
            "successful_runs": tenant.learning_state.successful_runs,
            "success_rate": (
                tenant.learning_state.successful_runs / tenant.learning_state.total_runs
                if tenant.learning_state.total_runs > 0 else 0
            ),
            "policy_updates": tenant.learning_state.policy_updates,
            "project_count": len(tenant.project_ids),
            "budget_used_pct": 0.0,  # TODO: integrate with cost tracking
            "is_active": tenant.is_active
        }
    
    def fork_policy(
        self,
        source_tenant_id: str,
        target_tenant_id: str,
        policy_type: str
    ) -> bool:
        """Fork a policy from one tenant to another"""
        source = self.get_tenant(source_tenant_id)
        target = self.get_tenant(target_tenant_id)
        
        if not source or not target:
            return False
        
        if not source.can_fork_policies:
            return False
        
        # Copy policy
        if policy_type == "planner":
            target.policy_space.planner_policies = dict(source.policy_space.planner_policies)
        elif policy_type == "tool":
            target.policy_space.tool_policies = dict(source.policy_space.tool_policies)
        elif policy_type == "agent":
            target.policy_space.agent_policies = dict(source.policy_space.agent_policies)
        elif policy_type == "generation":
            target.policy_space.generation_policies = dict(source.policy_space.generation_policies)
        else:
            return False
        
        self._save_tenant(target)
        return True
    
    def _load_tenants(self):
        """Load tenants from disk"""
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                path = os.path.join(self.storage_path, filename)
                try:
                    with open(path) as f:
                        data = json.load(f)
                        tenant = Tenant(**data)
                        self.tenants[tenant.tenant_id] = tenant
                except Exception as e:
                    print(f"Warning: Could not load tenant from {filename}: {e}")
    
    def _save_tenant(self, tenant: Tenant):
        """Save tenant to disk"""
        path = os.path.join(self.storage_path, f"{tenant.tenant_id}.json")
        with open(path, 'w') as f:
            f.write(tenant.model_dump_json(indent=2))


# Global tenant manager
_manager: Optional[TenantManager] = None

def get_tenant_manager() -> TenantManager:
    """Get global tenant manager"""
    global _manager
    if _manager is None:
        _manager = TenantManager()
    return _manager



