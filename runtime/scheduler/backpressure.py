"""
Backpressure signaling for orchestrator.
"""
from typing import Dict


def compute_backpressure(metrics: Dict[str, float]) -> str:
    """
    metrics: {queue_depth, cpu_util, gpu_util}
    returns: LOW | MEDIUM | HIGH
    """
    q = metrics.get("queue_depth", 0)
    cpu = metrics.get("cpu_util", 0)
    gpu = metrics.get("gpu_util", 0)
    if q > 200 or cpu > 0.9 or gpu > 0.9:
        return "HIGH"
    if q > 50 or cpu > 0.7 or gpu > 0.7:
        return "MEDIUM"
    return "LOW"


