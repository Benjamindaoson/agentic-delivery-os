"""
Runtime capability snapshot and tool quality cache.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime
import hashlib


@dataclass
class ToolCapability:
    name: str
    version: str
    available: bool
    recent_failure_rate: float
    queue_depth: int
    structure_stability: float = 0.8
    numeric_consistency: float = 0.8
    failure_rate: float = 0.05


def capture_runtime_capabilities(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    snapshot = {
        "tools": [asdict(ToolCapability(**t)) for t in tools],
        "captured_at": datetime.now().isoformat(),
    }
    snapshot["capability_hash"] = hashlib.sha256(str(snapshot).encode()).hexdigest()
    return snapshot


