from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Iterable, List

import yaml


CONTINUOUS_EVAL_CFG = os.path.join("configs", "continuous_eval.yaml")
EVAL_HISTORY_PATH = os.path.join("artifacts", "continuous_eval_history.jsonl")


def _load_continuous_cfg() -> Dict[str, Any]:
    if not os.path.exists(CONTINUOUS_EVAL_CFG):
        return {"sampling_rate": 0.0, "max_daily_eval": 0, "shadow_mode": True}
    with open(CONTINUOUS_EVAL_CFG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _should_sample(request_id: str, sampling_rate: float) -> bool:
    if sampling_rate <= 0.0:
        return False
    h = hashlib.sha256(request_id.encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return bucket < sampling_rate


def schedule_continuous_eval(request_ids: Iterable[str]) -> List[str]:
    """
    Deterministically select a subset of request_ids for continuous eval
    based on sampling_rate and max_daily_eval, and append them to history.
    """
    cfg = _load_continuous_cfg()
    sampling_rate = float(cfg.get("sampling_rate", 0.0))
    max_daily_eval = int(cfg.get("max_daily_eval", 0))

    selected: List[str] = []
    for rid in request_ids:
        if _should_sample(rid, sampling_rate):
            selected.append(rid)
            if max_daily_eval and len(selected) >= max_daily_eval:
                break

    if selected:
        os.makedirs(os.path.dirname(EVAL_HISTORY_PATH), exist_ok=True)
        with open(EVAL_HISTORY_PATH, "a", encoding="utf-8") as f:
            for rid in selected:
                entry = {"request_id": rid, "scheduled": True}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return selected



