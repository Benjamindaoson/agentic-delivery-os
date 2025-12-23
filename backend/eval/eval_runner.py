from __future__ import annotations

import json
import os
from typing import Any, Dict

from .coverage_matrix import build_coverage_matrix


def write_eval_report(eval_report: Dict[str, Any], path: str) -> str:
    """
    Attach coverage_matrix to eval_report and persist it to the given path.
    This is a helper to be used by higher-level eval flows.
    """
    coverage = build_coverage_matrix(eval_report)
    eval_report = dict(eval_report)  # shallow copy
    eval_report["coverage_matrix"] = coverage

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2, ensure_ascii=False)
    return path
































