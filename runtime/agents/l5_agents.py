from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime

class AgentPerformance(BaseModel):
    model_config = ConfigDict(extra='allow')
    success_rate: float = 0.0
    total_runs: int = 0
    avg_latency: float = 0.0
    avg_cost: float = 0.0
    failure_modes: Dict[str, int] = {}
    task_type_affinity: Dict[str, float] = {}

class AgentProfile(BaseModel):
    model_config = ConfigDict(extra='allow')
    agent_id: str
    role_name: Optional[str] = "GenericAgent"
    description: Optional[str] = "L5 Agent"
    capabilities: List[str] = Field(default_factory=list)
    performance: Optional[AgentPerformance] = None
    created_at: Any = Field(default_factory=datetime.now)
    last_active: Any = Field(default_factory=datetime.now)
    schema_version: str = "1.0"

class AgentPolicy(BaseModel):
    model_config = ConfigDict(extra='allow')
    policy_version: str
    agent_id: str
    rules: Dict[str, Any]
    diff_from_previous: Optional[str] = None
    status: str = "active"
    promoted_at: Optional[datetime] = None

class AgentManager:
    def __init__(self, profile_path: str = "artifacts/agent_profiles", policy_path: str = "artifacts/agent_policies"):
        self.profile_path = profile_path
        self.policy_path = policy_path
        os.makedirs(profile_path, exist_ok=True)
        os.makedirs(policy_path, exist_ok=True)

    def get_profile(self, agent_id: str) -> AgentProfile:
        path = f"{self.profile_path}/{agent_id}.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                return AgentProfile(**data)
        return AgentProfile(agent_id=agent_id)

    def save_profile(self, profile: AgentProfile):
        profile.last_active = datetime.now()
        profile.updated_at = datetime.now().isoformat()
        with open(f"{self.profile_path}/{profile.agent_id}.json", "w") as f:
            f.write(profile.model_dump_json(indent=2))

    def update_performance(self, agent_id: str, success: bool, latency: float, cost: float, task_type: str, failure_type: Optional[str] = None):
        profile = self.get_profile(agent_id)
        if not profile.performance:
            profile.performance = AgentPerformance()
            
        p = profile.performance
        n = p.total_runs
        
        p.success_rate = (p.success_rate * n + (1.0 if success else 0.0)) / (n + 1)
        p.avg_latency = (p.avg_latency * n + latency) / (n + 1)
        p.avg_cost = (p.avg_cost * n + cost) / (n + 1)
        p.total_runs += 1
        
        if not success and failure_type:
            p.failure_modes[failure_type] = p.failure_modes.get(failure_type, 0) + 1
        
        p.task_type_affinity[task_type] = p.task_type_affinity.get(task_type, 0.0) * 0.9 + (1.0 if success else 0.0) * 0.1
        
        # Also update flattened fields if they exist in artifact
        if hasattr(profile, "total_runs"):
            setattr(profile, "total_runs", getattr(profile, "total_runs", 0) + 1)
            if success:
                setattr(profile, "successful_runs", getattr(profile, "successful_runs", 0) + 1)
        
        self.save_profile(profile)

    def create_policy(self, agent_id: str, rules: Dict[str, Any], version: str) -> AgentPolicy:
        policy = AgentPolicy(policy_version=version, agent_id=agent_id, rules=rules)
        with open(f"{self.policy_path}/{version}.json", "w") as f:
            f.write(policy.model_dump_json(indent=2))
        return policy
