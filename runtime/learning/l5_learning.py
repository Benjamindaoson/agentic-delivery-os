from typing import List, Dict, Any, Optional
import os
import json
from datetime import datetime
from pydantic import BaseModel

class PromotionTrace(BaseModel):
    policy_id: str
    from_version: str
    to_version: str
    rationale: str
    metrics_delta: Dict[str, float]
    timestamp: datetime = datetime.now()

class LearningController:
    def __init__(self, artifact_path: str = "artifacts/learning"):
        self.artifact_path = artifact_path
        os.makedirs(artifact_path, exist_ok=True)

    def aggregate_rewards(self, run_ids: List[str]) -> float:
        return 0.85

    def promote_policy(self, agent_id: str, rationale: str, delta: Dict[str, float]):
        trace = PromotionTrace(
            policy_id=agent_id,
            from_version="v1.0",
            to_version="v1.1",
            rationale=rationale,
            metrics_delta=delta
        )
        timestamp_str = datetime.now().isoformat().replace(":", "_")
        path = f"{self.artifact_path}/promotions_{timestamp_str}.json"
        with open(path, "w") as f:
            f.write(trace.model_dump_json(indent=2))
        return trace
