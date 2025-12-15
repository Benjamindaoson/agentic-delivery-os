"""
Trade-off analyzer for Data Intelligence Agent.
Detects trade-offs deterministically across strategies.
"""

from typing import List, Dict


class TradeoffLabel:
    RESOLVABLE = "RESOLVABLE"
    NON_RESOLVABLE = "NON_RESOLVABLE"


def _detect_tradeoffs(strategies: List[Dict]) -> List[Dict]:
    """
    Detect tradeoffs among candidate strategies.
    Heuristics:
    - cost vs accuracy
    - latency vs accuracy
    - completeness (heavy vs minimal)
    """
    tradeoffs = []
    if len(strategies) < 2:
        return tradeoffs

    # Extract numeric proxies
    costs = [s.get("cost_estimate", 0) for s in strategies]
    accuracies = [s.get("accuracy_band", "medium") for s in strategies]
    latencies = [s.get("latency_class", "medium") for s in strategies]

    cost_range = (min(costs), max(costs))
    latency_range = (min(latencies), max(latencies))

    # Helper: accuracy score mapping
    acc_score = {"low": 0, "medium": 1, "high": 2}
    acc_values = [acc_score.get(a, 1) for a in accuracies]
    acc_range = (min(acc_values), max(acc_values))

    # Cost vs Accuracy tradeoff
    if cost_range[1] > cost_range[0] and acc_range[1] > acc_range[0]:
        tradeoffs.append(
            {
                "tradeoff_type": "cost_accuracy",
                "label": TradeoffLabel.RESOLVABLE
                if (cost_range[1] - cost_range[0]) <= 1.0
                else TradeoffLabel.NON_RESOLVABLE,
                "evidence": {
                    "cost_range": cost_range,
                    "accuracy_range": acc_range,
                },
            }
        )

    # Latency vs Accuracy tradeoff
    latency_score = {"low": 0, "medium": 1, "high": 2}
    lat_values = [latency_score.get(l, 1) for l in latencies]
    lat_range = (min(lat_values), max(lat_values))
    if lat_range[1] > lat_range[0] and acc_range[1] > acc_range[0]:
        tradeoffs.append(
            {
                "tradeoff_type": "speed_quality",
                "label": TradeoffLabel.RESOLVABLE
                if (lat_range[1] - lat_range[0]) <= 1
                else TradeoffLabel.NON_RESOLVABLE,
                "evidence": {
                    "latency_range": latency_range,
                    "accuracy_range": acc_range,
                },
            }
        )

    # Completeness (heavy vs minimal)
    has_minimal = any("metadata_only" in s.get("pipeline_steps", []) for s in strategies)
    has_full = any("text_extract:native" in s.get("pipeline_steps", []) or "ocr:" in " ".join(s.get("pipeline_steps", [])) for s in strategies)
    if has_minimal and has_full:
        tradeoffs.append(
            {
                "tradeoff_type": "completeness",
                "label": TradeoffLabel.NON_RESOLVABLE,
                "evidence": {"minimal": True, "full": True},
            }
        )

    # Mark overall non-resolvable if multiple conflicts persist
    if len(tradeoffs) >= 2:
        tradeoffs.append(
            {
                "tradeoff_type": "aggregate_conflict",
                "label": TradeoffLabel.NON_RESOLVABLE,
                "evidence": {"count": len(tradeoffs)},
            }
        )

    return tradeoffs


def analyze(file_strategies: List[Dict]) -> List[Dict]:
    """
    Analyze tradeoffs for each file.
    """
    results = []
    for entry in file_strategies:
        strategies = entry.get("strategies", [])
        results.append(
            {
                "file_path": entry.get("file_path"),
                "tradeoffs": _detect_tradeoffs(strategies),
            }
        )
    return results
