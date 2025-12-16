"""
HITL Learning Engine (Phase 8 · P5-1)

This module consumes HITL patches and current strategy snapshots,
and produces deterministic learning updates that can be applied to
parser strategies, chunk policies, and numeric-first routing weights.

It does NOT directly mutate live configs; it only writes
artifacts/learning_updates.json for later review & application.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


LEARNING_UPDATES_PATH = os.path.join("artifacts", "learning_updates.json")


@dataclass
class LearningUpdate:
    kind: str
    key: str
    delta: float
    reason: str


def apply_hitl_learning(
    hitl_patch: Dict[str, Any],
    dq_report: Dict[str, Any],
    parser_strategy: Dict[str, Any],
    chunk_policy: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply learning logic based on a single HITL patch.

    - OCR / table_cell patch → increase parser strategy prior
    - chunk_boundary patch   → adjust chunk policy parameters
    - numeric patch          → increase numeric_first routing weight

    Returns an update summary and writes artifacts/learning_updates.json.
    """
    updates: List[LearningUpdate] = []
    patch_type = hitl_patch.get("patch_type")

    if patch_type in ("ocr_cell", "table_cell"):
        updates.append(
            LearningUpdate(
                kind="parser_strategy_prior",
                key="ocr_or_table",
                delta=0.1,
                reason="HITL patch on OCR/table cell",
            )
        )
    if patch_type == "chunk_boundary":
        updates.append(
            LearningUpdate(
                kind="chunk_policy",
                key="boundary_sensitivity",
                delta=0.1,
                reason="HITL patch on chunk boundary",
            )
        )
    if patch_type == "numeric_cell":
        updates.append(
            LearningUpdate(
                kind="numeric_first_weight",
                key="numeric_first",
                delta=0.1,
                reason="HITL patch on numeric cell",
            )
        )

    summary: Dict[str, Any] = {
        "job_id": hitl_patch.get("job_id"),
        "patch_type": patch_type,
        "updates": [asdict(u) for u in updates],
    }

    os.makedirs(os.path.dirname(LEARNING_UPDATES_PATH), exist_ok=True)
    with open(LEARNING_UPDATES_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary





