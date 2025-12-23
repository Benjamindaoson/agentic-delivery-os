"""
Semantic Task Success Reward

Computes a normalized task success score (0~1) using:
- quality_score
- grounding_score
- cost_efficiency
- user_intent_match

All rewards are traceable and appended to artifacts/reward_trace.json.
"""
from __future__ import annotations

import os
import json
from typing import Dict, Any, Tuple
from datetime import datetime


def compute_semantic_reward(
    *,
    quality_score: float,
    grounding_score: float,
    cost_efficiency: float,
    user_intent_match: float,
    weights: Dict[str, float] = None,
    task_id: str = None,
    artifacts_dir: str = "artifacts"
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute semantic task success score and persist trace.

    Returns:
        (reward_value, detail_dict)
    """
    w = weights or {
        "quality": 0.35,
        "grounding": 0.25,
        "cost": 0.20,
        "intent": 0.20,
    }

    # Clamp inputs
    def clamp(v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    quality_score = clamp(quality_score)
    grounding_score = clamp(grounding_score)
    cost_efficiency = clamp(cost_efficiency)
    user_intent_match = clamp(user_intent_match)

    reward = (
        quality_score * w["quality"]
        + grounding_score * w["grounding"]
        + cost_efficiency * w["cost"]
        + user_intent_match * w["intent"]
    )

    detail = {
        "timestamp": datetime.now().isoformat(),
        "quality_score": quality_score,
        "grounding_score": grounding_score,
        "cost_efficiency": cost_efficiency,
        "user_intent_match": user_intent_match,
        "weights": w,
        "reward": reward,
    }

    if task_id:
        _append_reward_trace(task_id, detail, artifacts_dir=artifacts_dir)

    return reward, detail


def _append_reward_trace(task_id: str, detail: Dict[str, Any], artifacts_dir: str = "artifacts"):
    """Append reward trace entry to artifacts/reward_trace.json."""
    trace_path = os.path.join(artifacts_dir, "reward_trace.json")
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)

    entry = {
        "task_id": task_id,
        **detail,
    }

    try:
        existing = []
        if os.path.exists(trace_path):
            with open(trace_path, "r", encoding="utf-8") as f:
                existing = json.load(f) or []
        existing.append(entry)
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception:
        # Best-effort persistence
        pass

