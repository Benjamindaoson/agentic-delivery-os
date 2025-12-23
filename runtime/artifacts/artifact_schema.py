"""
Artifact schema helpers for L5.5 exploration/learning.

Each artifact must include:
- schema_version
- timestamp
- ids (run_id / candidate_id / policy_id)
- inputs_hash (for replay)
- decision / rationale / metrics / links
"""
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime


DEFAULT_SCHEMA_VERSION = "1.0"


def compute_inputs_hash(payload: Dict[str, Any]) -> str:
    """Compute stable hash for replayable inputs."""
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class ArtifactBase:
    schema_version: str = DEFAULT_SCHEMA_VERSION
    timestamp: str = ""
    inputs_hash: str = ""

    def finalize(self, payload: Dict[str, Any]) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.inputs_hash:
            self.inputs_hash = compute_inputs_hash(payload)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



