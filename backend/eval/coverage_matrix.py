from __future__ import annotations

from typing import Any, Dict, List


_COVERAGE_KEYS = {
    "offline.parse.ocr": ["offline", "parse", "ocr"],
    "offline.chunk.stability": ["offline", "chunk", "stability"],
    "online.retrieval.recall@k": ["online", "retrieval", "recall@k"],
    "online.rerank": ["online", "rerank"],
    "online.verification.coverage": ["online", "verification", "coverage"],
    "hitl.fix_rate": ["hitl", "fix_rate"],
    "cost.budget": ["cost", "budget"],
    "latency.slo": ["latency", "slo"],
}


def _has_path(metrics: Dict[str, Any], path: List[str]) -> bool:
    cur: Any = metrics
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def build_coverage_matrix(eval_report: dict) -> dict:
    """
    Build a coverage matrix based on the presence of metrics in eval_report.

    Rules:
    - metric path present in eval_report["metrics"] → covered=True
    - otherwise → covered=False
    """
    metrics: Dict[str, Any] = eval_report.get("metrics", {})
    matrix: Dict[str, Dict[str, Any]] = {}
    for name, path in _COVERAGE_KEYS.items():
        covered = _has_path(metrics, path)
        matrix[name] = {"covered": bool(covered)}
    return matrix
































