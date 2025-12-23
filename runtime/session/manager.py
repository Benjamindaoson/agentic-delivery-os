from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import os
import uuid

class SessionStats(BaseModel):
    total_runs: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    total_cost: float = 0.0

class SessionMemory(BaseModel):
    last_task_type: Optional[str] = None
    context_summary: str = ""
    learned_preferences: Dict[str, Any] = {}

class SessionPolicy(BaseModel):
    max_cost_limit: float = 10.0
    allowed_tools: List[str] = ["*"]
    risk_threshold: str = "medium"

class Session(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_active_at: datetime = Field(default_factory=datetime.now)
    stats: SessionStats = Field(default_factory=SessionStats)
    memory: SessionMemory = Field(default_factory=SessionMemory)
    policy: SessionPolicy = Field(default_factory=SessionPolicy)
    run_ids: List[str] = []

class SessionManager:
    def __init__(self, storage_path: str = "artifacts/session"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)

    def get_or_create_session(self, session_id: Optional[str] = None, user_id: str = "default_user") -> Session:
        if session_id and os.path.exists(f"{self.storage_path}/{session_id}.json"):
            with open(f"{self.storage_path}/{session_id}.json", "r") as f:
                data = json.load(f)
                return Session(**data)
        
        new_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        session = Session(session_id=new_id, user_id=user_id)
        self.save_session(session)
        return session

    def save_session(self, session: Session):
        session.last_active_at = datetime.now()
        with open(f"{self.storage_path}/{session.session_id}.json", "w") as f:
            f.write(session.model_dump_json(indent=2))

    def add_run_to_session(self, session_id: str, run_id: str):
        session = self.get_or_create_session(session_id)
        if run_id not in session.run_ids:
            session.run_ids.append(run_id)
            self.save_session(session)



