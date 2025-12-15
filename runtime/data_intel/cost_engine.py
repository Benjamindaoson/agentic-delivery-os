"""
Additive Cost Model with forecast/attribution.
"""
from typing import Dict, Any
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class CostBreakdown:
    sampling: float
    parsing: float
    ocr: float
    table_recovery: float
    post_process: float
    storage: float

    def total(self) -> float:
        return (
            self.sampling
            + self.parsing
            + self.ocr
            + self.table_recovery
            + self.post_process
            + self.storage
        )


def forecast_cost(signals: Dict[str, Any], strategies: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic forecast using cheap signals + strategy cost ranges.
    """
    # Simple deterministic mapping
    size = signals.get("size_bytes", 0)
    table_density = signals.get("cheap_signals", {}).get("table_boundary_heuristic", 0.2)
    image_density = signals.get("cheap_signals", {}).get("image_density", 0.2)

    sampling = 0.02 if size > 20_000_000 else 0.005
    parsing = 0.05
    ocr = 0.0
    table_recovery = 0.0
    post_process = 0.02
    storage = max(size / 1_000_000_000, 0.001)

    # Strategy-aware adjustments
    for s in strategies:
        pid = s.get("id") or s.get("policy_id")
        if pid and "ocr" in pid.lower():
            ocr = max(ocr, s.get("expected_cost_range", [0, 0])[1])
        if pid and "table" in pid.lower():
            table_recovery = max(table_recovery, s.get("expected_cost_range", [0, 0])[1] * table_density)

    cb = CostBreakdown(
        sampling=sampling,
        parsing=parsing,
        ocr=ocr,
        table_recovery=table_recovery,
        post_process=post_process,
        storage=storage,
    )
    total = cb.total()
    ci_low = total * 0.9
    ci_high = total * 1.2
    return {
        "cost_breakdown": asdict(cb),
        "total_cost_estimate": total,
        "confidence_interval": [ci_low, ci_high],
        "cost_hash": hashlib.sha256(f"{total}".encode()).hexdigest(),
    }


def reconcile(forecast: float, actual: float, signals: Dict[str, Any]) -> Dict[str, Any]:
    error = actual - forecast
    error_ratio = (error / forecast) if forecast else 0.0
    attributions = []
    if signals.get("cheap_signals", {}).get("image_density", 0) > 0.6:
        attributions.append("density_misjudge")
    if signals.get("cheap_signals", {}).get("table_boundary_heuristic", 0) > 0.6:
        attributions.append("table_misjudge")
    if not attributions:
        attributions.append("tool_degradation")
    return {
        "forecast_cost": forecast,
        "actual_cost": actual,
        "error_ratio": error_ratio,
        "error_attribution": attributions,
    }

