from pydantic import BaseModel
from typing import Optional, Literal

class SLOBudget(BaseModel):
    latency: Optional[float] = None
    cost: Optional[float] = None
    quality: Optional[float] = None

class DeliverySpec(BaseModel):
    """Delivery Spec 最小字段集"""
    audience: Optional[str] = None
    answerStyle: Optional[Literal["Strict", "Balanced", "Exploratory"]] = None
    mustCite: Optional[bool] = None
    dataSourceType: Optional[str] = None
    deploymentChannel: Optional[Literal["API", "Web", "Internal"]] = None
    sloBudget: Optional[SLOBudget] = None

class DeliverySpecResponse(BaseModel):
    taskId: str
    status: str




