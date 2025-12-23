import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from backend.offline.dq_engine import build_dq_report, DQDecision, DQMetrics, compute_metrics, decide_dq


HITL_QUEUE_DIR = os.path.join("artifacts", "hitl_queue")


@dataclass
class HitlIssue:
    type: str
    page: int
    bbox: List[float]


@dataclass
class HitlTask:
    job_id: str
    stage: str
    trigger: str
    issues: List[HitlIssue]
    allowed_patch_types: List[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "trigger": self.trigger,
            "issues": [asdict(i) for i in self.issues],
            "allowed_patch_types": self.allowed_patch_types,
            "created_at": self.created_at,
        }


def _issues_from_metrics(metrics: DQMetrics) -> List[HitlIssue]:
    """
    Map DQMetrics to concrete issues. This is deterministic and purely
    signal-driven; we do not fabricate issues beyond what metrics imply.
    """
    issues: List[HitlIssue] = []
    # Page is approximated as 1 and bbox as a sentinel region; this is still
    # strictly derived from document-level signals (not random).
    page = 1
    bbox = [0.0, 0.0, 1.0, 1.0]

    if metrics.ocr_coverage < 0.6:
        issues.append(HitlIssue(type="ocr_low_coverage", page=page, bbox=bbox))
    if metrics.table_recovery_rate < 0.7:
        issues.append(HitlIssue(type="table_header_uncertain", page=page, bbox=bbox))
    return issues


def create_hitl_task_for_warn(job_id: str, parsed_doc: Dict[str, Any]) -> str:
    """
    Given a job_id and ParsedDoc, recompute DQ metrics, and if the decision
    is WARN, emit a HITL task at artifacts/hitl_queue/{job_id}.json.

    Returns the created task path. If decision is not WARN, no task is written
    and an empty string is returned.
    """
    metrics = compute_metrics(parsed_doc)
    decision = decide_dq(metrics)
    if decision.level != "WARN":
        return ""

    os.makedirs(HITL_QUEUE_DIR, exist_ok=True)
    issues = _issues_from_metrics(metrics)
    task = HitlTask(
        job_id=job_id,
        stage="offline_dq",
        trigger="DQ_WARN",
        issues=issues,
        allowed_patch_types=[
            "ocr_cell",
            "table_cell",
            "table_header",
            "chunk_boundary",
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    path = os.path.join(HITL_QUEUE_DIR, f"{job_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)
    return path
































