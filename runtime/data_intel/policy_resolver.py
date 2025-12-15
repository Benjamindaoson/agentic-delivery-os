"""
Policy resolver for Data Intelligence Agent.
Applies tenant policy, tenant context, and system constraints.
"""

from typing import Dict, List, Any
import hashlib
from dataclasses import dataclass, asdict


class ResolutionStatus:
    AUTO_RESOLVED = "AUTO_RESOLVED"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    UNAUTHORIZED_TRADEOFF = "UNAUTHORIZED_TRADEOFF"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"


@dataclass
class PolicyResolution:
    status: str
    chosen_strategy_id: str
    rationale: Dict[str, Any]
    policy_hash: str
    tradeoff_violations: List[str]
    unattended_mode: bool


DEFAULT_POLICY = {
    "allowed_tradeoff_types": ["cost_accuracy", "speed_quality"],
    "auto_resolution_priority": "cost_first",
    "max_auto_cost_multiplier": 1.5,
    "max_accuracy_drop_tolerance": 1,
    "escalation_threshold": 2,
    "unattended_mode": True,
}


def _policy_hash(policy: Dict[str, Any]) -> str:
    if not policy:
        return "none"
    return hashlib.sha256(
        str(sorted(policy.items())).encode("utf-8")
    ).hexdigest()


def _priority_sort(strategies: List[Dict], priority: str) -> List[Dict]:
    # Lower cost preferred for cost_first; higher accuracy for quality_first; lower latency for speed_first
    def score(s: Dict) -> float:
        if priority == "cost_first":
            return s.get("cost_estimate", 0.0)
        if priority == "quality_first":
            acc = s.get("accuracy_band", "medium")
            return {"high": 0, "medium": 1, "low": 2}.get(acc, 1)
        if priority == "speed_first":
            lat = s.get("latency_class", "medium")
            return {"low": 0, "medium": 1, "high": 2}.get(lat, 1)
        return s.get("cost_estimate", 0.0)

    return sorted(strategies, key=score)


def resolve(
    file_entry: Dict,
    tradeoff_entry: Dict,
    tenant_policy: Dict[str, Any],
    tenant_context: Dict[str, Any],
    system_constraints: Dict[str, Any],
) -> Dict:
    """
    Resolve tradeoffs and choose a strategy.
    """
    policy = tenant_policy or {}
    policy = {**DEFAULT_POLICY, **policy}  # merge defaults
    unattended_mode = bool(tenant_context.get("unattended_mode", policy["unattended_mode"]))
    allowed_tradeoffs = policy.get("allowed_tradeoff_types", [])
    priority = policy.get("auto_resolution_priority", "cost_first")

    strategies = file_entry.get("strategies", [])
    tradeoffs = tradeoff_entry.get("tradeoffs", [])

    policy_hash_val = _policy_hash(policy)

    # No policy provided and tradeoffs exist -> UNAUTHORIZED
    if tenant_policy is None and tradeoffs:
        return asdict(
            PolicyResolution(
                status=ResolutionStatus.UNAUTHORIZED_TRADEOFF,
                chosen_strategy_id="",
                rationale={"reason": "no_tenant_policy", "tradeoffs": tradeoffs},
                policy_hash=policy_hash_val,
                tradeoff_violations=[t.get("tradeoff_type") for t in tradeoffs],
                unattended_mode=unattended_mode,
            )
        )

    # Check tradeoffs against policy thresholds
    violations = []
    for t in tradeoffs:
        t_type = t.get("tradeoff_type")
        label = t.get("label")
        if t_type not in allowed_tradeoffs:
            violations.append(t_type)
            continue
        if label == "NON_RESOLVABLE" and policy.get("max_auto_cost_multiplier", 1) < 2:
            violations.append(t_type)

    if violations:
        return asdict(
            PolicyResolution(
                status=ResolutionStatus.POLICY_VIOLATION,
                chosen_strategy_id="",
                rationale={"violations": violations},
                policy_hash=policy_hash_val,
                tradeoff_violations=violations,
                unattended_mode=unattended_mode,
            )
        )

    # unattended_mode true: must auto-resolve or fail
    sorted_strategies = _priority_sort(strategies, priority)
    if unattended_mode and not sorted_strategies:
        return asdict(
            PolicyResolution(
                status=ResolutionStatus.AUTHORIZATION_REQUIRED,
                chosen_strategy_id="",
                rationale={"reason": "no_strategy_available"},
                policy_hash=policy_hash_val,
                tradeoff_violations=[],
                unattended_mode=unattended_mode,
            )
        )
    chosen = sorted_strategies[0] if sorted_strategies else {}

    return asdict(
        PolicyResolution(
            status=ResolutionStatus.AUTO_RESOLVED,
            chosen_strategy_id=chosen.get("id", ""),
            rationale={
                "priority": priority,
                "unattended_mode": unattended_mode,
                "tradeoffs": tradeoffs,
            },
            policy_hash=policy_hash_val,
            tradeoff_violations=[],
            unattended_mode=unattended_mode,
        )
    )
