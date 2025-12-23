"""
Agent Policy Binding: Bind policy versions to agent roles.
L5-grade: Policy bindings are explicit, shadow-compatible, never affect active run.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class PolicyBinding:
    """Binding between an agent role and a policy version."""
    binding_id: str
    agent_id: str
    role_id: str
    policy_id: str
    policy_version: str
    
    # Binding type
    binding_type: str = "active"  # active, shadow, candidate
    
    # Scope
    run_id: Optional[str] = None  # None = global binding
    task_types: List[str] = field(default_factory=list)  # Empty = all tasks
    
    # Constraints
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    priority: int = 5  # Higher priority bindings override lower
    
    # Metadata
    created_at: str = ""
    created_by: str = "system"
    rationale: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def is_effective(self) -> bool:
        """Check if binding is currently effective."""
        now = datetime.now().isoformat()
        
        if self.effective_from and now < self.effective_from:
            return False
        if self.effective_until and now > self.effective_until:
            return False
        
        return True


@dataclass
class PolicyBindingSet:
    """Set of policy bindings for a run."""
    run_id: str
    bindings: List[PolicyBinding]
    
    # Shadow bindings (separate for A/B)
    shadow_bindings: List[PolicyBinding] = field(default_factory=list)
    
    # Resolution result
    resolved_policies: Dict[str, str] = field(default_factory=dict)  # agent_id -> policy_id
    
    # Metadata
    created_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "bindings": [b.to_dict() for b in self.bindings],
            "shadow_bindings": [b.to_dict() for b in self.shadow_bindings],
            "resolved_policies": self.resolved_policies,
            "created_at": self.created_at,
            "schema_version": self.schema_version
        }


class AgentPolicyBindingRegistry:
    """
    Registry for agent-policy bindings.
    
    Supports:
    - Active bindings (affect execution)
    - Shadow bindings (for A/B comparison, never affect output)
    - Candidate bindings (for evaluation before promotion)
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.bindings_dir = os.path.join(artifacts_dir, "agents", "policy_binding")
        os.makedirs(self.bindings_dir, exist_ok=True)
        
        self._global_bindings: List[PolicyBinding] = []
        self._load_global_bindings()
    
    def bind(
        self,
        agent_id: str,
        role_id: str,
        policy_id: str,
        policy_version: str,
        binding_type: str = "active",
        run_id: Optional[str] = None,
        task_types: Optional[List[str]] = None,
        priority: int = 5,
        rationale: str = ""
    ) -> PolicyBinding:
        """
        Create a policy binding.
        
        Args:
            agent_id: Agent to bind
            role_id: Role the agent plays
            policy_id: Policy to bind
            policy_version: Policy version
            binding_type: active, shadow, or candidate
            run_id: Specific run (None for global)
            task_types: Specific task types (empty for all)
            priority: Binding priority
            rationale: Reason for binding
            
        Returns:
            PolicyBinding
        """
        binding = PolicyBinding(
            binding_id=self._generate_binding_id(agent_id, policy_id, run_id),
            agent_id=agent_id,
            role_id=role_id,
            policy_id=policy_id,
            policy_version=policy_version,
            binding_type=binding_type,
            run_id=run_id,
            task_types=task_types or [],
            priority=priority,
            rationale=rationale
        )
        
        if run_id is None:
            # Global binding
            self._global_bindings.append(binding)
            self._save_global_bindings()
        else:
            # Run-specific binding
            self._save_run_binding(binding)
        
        return binding
    
    def resolve_binding(
        self,
        agent_id: str,
        role_id: str,
        run_id: str,
        task_type: Optional[str] = None,
        include_shadow: bool = False
    ) -> Optional[PolicyBinding]:
        """
        Resolve the effective policy binding for an agent/role.
        
        Resolution priority:
        1. Run-specific bindings (highest)
        2. Global bindings by priority
        3. Task-type specific bindings
        
        Args:
            agent_id: Agent ID
            role_id: Role ID
            run_id: Run ID
            task_type: Optional task type
            include_shadow: Include shadow bindings
            
        Returns:
            Resolved PolicyBinding or None
        """
        candidates = []
        
        # Collect run-specific bindings
        run_bindings = self._load_run_bindings(run_id)
        candidates.extend(run_bindings)
        
        # Collect global bindings
        candidates.extend(self._global_bindings)
        
        # Filter
        filtered = []
        for binding in candidates:
            if binding.agent_id != agent_id:
                continue
            if binding.role_id != role_id:
                continue
            if not binding.is_effective():
                continue
            if not include_shadow and binding.binding_type == "shadow":
                continue
            if binding.task_types and task_type and task_type not in binding.task_types:
                continue
            
            filtered.append(binding)
        
        if not filtered:
            return None
        
        # Sort by priority (highest first), then by specificity
        def binding_score(b: PolicyBinding) -> tuple:
            specificity = 0
            if b.run_id:
                specificity += 10
            if b.task_types:
                specificity += 5
            return (b.priority, specificity)
        
        filtered.sort(key=binding_score, reverse=True)
        
        return filtered[0]
    
    def create_binding_set(
        self,
        run_id: str,
        agent_role_pairs: List[tuple]
    ) -> PolicyBindingSet:
        """
        Create a complete binding set for a run.
        
        Args:
            run_id: Run ID
            agent_role_pairs: List of (agent_id, role_id) tuples
            
        Returns:
            PolicyBindingSet with resolved policies
        """
        active_bindings = []
        shadow_bindings = []
        resolved = {}
        
        for agent_id, role_id in agent_role_pairs:
            # Resolve active
            active = self.resolve_binding(agent_id, role_id, run_id, include_shadow=False)
            if active:
                active_bindings.append(active)
                resolved[agent_id] = active.policy_id
            
            # Resolve shadow
            shadow = self.resolve_binding(agent_id, role_id, run_id, include_shadow=True)
            if shadow and shadow.binding_type == "shadow":
                shadow_bindings.append(shadow)
        
        binding_set = PolicyBindingSet(
            run_id=run_id,
            bindings=active_bindings,
            shadow_bindings=shadow_bindings,
            resolved_policies=resolved
        )
        
        # Save artifact
        self._save_binding_set(binding_set)
        
        return binding_set
    
    def get_shadow_bindings(self, run_id: str) -> List[PolicyBinding]:
        """Get shadow bindings for a run (never affect active output)."""
        run_bindings = self._load_run_bindings(run_id)
        return [b for b in run_bindings if b.binding_type == "shadow"]
    
    def promote_binding(
        self,
        binding_id: str,
        from_type: str,
        to_type: str
    ) -> bool:
        """
        Promote a binding (e.g., candidate -> active).
        
        Args:
            binding_id: Binding to promote
            from_type: Expected current type
            to_type: New type
            
        Returns:
            True if promoted, False if not found or wrong type
        """
        for binding in self._global_bindings:
            if binding.binding_id == binding_id:
                if binding.binding_type != from_type:
                    return False
                binding.binding_type = to_type
                self._save_global_bindings()
                return True
        
        return False
    
    def _generate_binding_id(
        self,
        agent_id: str,
        policy_id: str,
        run_id: Optional[str]
    ) -> str:
        """Generate binding ID."""
        import hashlib
        content = f"{agent_id}:{policy_id}:{run_id or 'global'}:{datetime.now().isoformat()}"
        return f"bind_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _save_global_bindings(self) -> None:
        """Save global bindings."""
        path = os.path.join(self.bindings_dir, "global_bindings.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "bindings": [b.to_dict() for b in self._global_bindings],
                "updated_at": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    
    def _load_global_bindings(self) -> None:
        """Load global bindings."""
        path = os.path.join(self.bindings_dir, "global_bindings.json")
        if not os.path.exists(path):
            return
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for b_data in data.get("bindings", []):
            self._global_bindings.append(PolicyBinding(**b_data))
    
    def _save_run_binding(self, binding: PolicyBinding) -> None:
        """Save run-specific binding."""
        if not binding.run_id:
            return
        
        path = os.path.join(self.bindings_dir, f"{binding.run_id}.json")
        
        # Load existing or create new
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "run_id": binding.run_id,
                "schema_version": "1.0",
                "bindings": []
            }
        
        data["bindings"].append(binding.to_dict())
        data["updated_at"] = datetime.now().isoformat()
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_run_bindings(self, run_id: str) -> List[PolicyBinding]:
        """Load run-specific bindings."""
        path = os.path.join(self.bindings_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return []
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return [PolicyBinding(**b) for b in data.get("bindings", [])]
    
    def _save_binding_set(self, binding_set: PolicyBindingSet) -> None:
        """Save binding set artifact."""
        path = os.path.join(self.bindings_dir, f"{binding_set.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(binding_set.to_dict(), f, indent=2, ensure_ascii=False)



