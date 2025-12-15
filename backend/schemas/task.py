from pydantic import BaseModel
from typing import Optional, Literal

class TaskProgress(BaseModel):
    currentAgent: Optional[str] = None
    currentStep: Optional[str] = None

class TaskStatusResponse(BaseModel):
    taskId: str
    state: Literal["IDLE", "SPEC_READY", "RUNNING", "FAILED", "COMPLETED"]
    error: Optional[str] = None
    progress: Optional[TaskProgress] = None


