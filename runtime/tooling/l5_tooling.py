from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Any, Optional
import json
import os
from datetime import datetime

class ToolStats(BaseModel):
    model_config = ConfigDict(extra='allow')
    total_uses: int = 0
    failure_count: int = 0
    avg_latency: float = 0.0
    roi_score: float = 0.0
    risk_level: str = "low"

class ToolProfile(BaseModel):
    model_config = ConfigDict(extra='allow')
    tool_id: str
    tool_name: Optional[str] = None
    description: Optional[str] = "L5 Tool"
    stats: Optional[ToolStats] = None
    is_enabled: bool = True
    last_failure: Optional[datetime] = None
    schema_version: str = "1.0"

class ToolFailure(BaseModel):
    model_config = ConfigDict(extra='allow')
    run_id: str
    tool_id: str
    error_message: str
    stack_trace: Optional[str] = None
    recovered: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)

class ToolManager:
    def __init__(self, profile_path: str = "artifacts/tool_profiles", failure_path: str = "artifacts/tool_failures"):
        self.profile_path = profile_path
        self.failure_path = failure_path
        os.makedirs(profile_path, exist_ok=True)
        os.makedirs(failure_path, exist_ok=True)

    def get_profile(self, tool_id: str) -> ToolProfile:
        path = f"{self.profile_path}/{tool_id}.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                # Handle field mapping from existing artifacts
                if "tool_name" not in data and "name" in data:
                    data["tool_name"] = data["name"]
                return ToolProfile(**data)
        return ToolProfile(tool_id=tool_id, tool_name=tool_id)

    def save_profile(self, profile: ToolProfile):
        path = f"{self.profile_path}/{profile.tool_id}.json"
        with open(path, "w") as f:
            f.write(profile.model_dump_json(indent=2))

    def record_usage(self, tool_id: str, success: bool, latency: float, cost: float, value: float = 1.0):
        profile = self.get_profile(tool_id)
        
        # If stats object is missing or from different schema, initialize it
        if not profile.stats:
            profile.stats = ToolStats()
            
        s = profile.stats
        
        # Handle cases where existing artifact might have flattened stats
        # For simplicity in this L5 upgrade, we'll try to update the profile fields directly if they exist
        
        # Check if we should update flattened fields (like in the existing artifact)
        if hasattr(profile, "total_invocations"):
            profile.total_invocations = getattr(profile, "total_invocations", 0) + 1
            if success:
                profile.successful_invocations = getattr(profile, "successful_invocations", 0) + 1
            else:
                profile.failed_invocations = getattr(profile, "failed_invocations", 0) + 1
        
        # Update our schema stats
        n = s.total_uses
        s.avg_latency = (s.avg_latency * n + latency) / (n + 1)
        s.total_uses += 1
        if not success:
            s.failure_count += 1
            profile.last_failure = datetime.now()
        
        profile.updated_at = datetime.now().isoformat()
        self.save_profile(profile)

    def record_failure(self, run_id: str, tool_id: str, error: str, recovered: bool = False):
        failure = ToolFailure(run_id=run_id, tool_id=tool_id, error_message=error, recovered=recovered)
        path = f"{self.failure_path}/{run_id}.json"
        failures = []
        if os.path.exists(path):
            with open(path, "r") as f:
                failures = json.load(f)
        failures.append(failure.model_dump())
        with open(path, "w") as f:
            json.dump(failures, f, indent=2)
