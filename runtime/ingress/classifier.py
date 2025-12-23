from pydantic import BaseModel
from typing import Dict, Any, List
import json
import os
from datetime import datetime

class TaskClassification(BaseModel):
    run_id: str
    task_type: str
    intent: str
    complexity: str  # simple, moderate, complex
    required_capabilities: List[str]
    suggested_planner: str
    timestamp: datetime = datetime.now()

class TaskTypeClassifier:
    def __init__(self, artifact_path: str = "artifacts/task_type"):
        self.artifact_path = artifact_path
        os.makedirs(artifact_path, exist_ok=True)

    def classify(self, run_id: str, query: str) -> TaskClassification:
        # Simplified classification logic for L5 foundation
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["what is", "how to", "why"]):
            task_type = "rag_qa"
            intent = "informational"
            complexity = "moderate"
            capabilities = ["retrieval", "reasoning"]
            planner = "sequential_reasoner"
        elif any(word in query_lower for word in ["create", "build", "write"]):
            task_type = "generation"
            intent = "creative"
            complexity = "complex"
            capabilities = ["generation", "structuring"]
            planner = "iterative_refiner"
        else:
            task_type = "general_task"
            intent = "execution"
            complexity = "simple"
            capabilities = ["tool_use"]
            planner = "reactive_agent"

        classification = TaskClassification(
            run_id=run_id,
            task_type=task_type,
            intent=intent,
            complexity=complexity,
            required_capabilities=capabilities,
            suggested_planner=planner
        )
        
        self._save_artifact(classification)
        return classification

    def _save_artifact(self, classification: TaskClassification):
        path = f"{self.artifact_path}/{classification.run_id}.json"
        with open(path, "w") as f:
            f.write(classification.model_dump_json(indent=2))



