"""
Metrics registry for evaluation agent.
"""
METRICS = {
    "evidence_coverage": {"type": "hard", "pass_fail": True},
    "citation_consistency": {"type": "hard", "pass_fail": True},
    "policy_permission": {"type": "hard", "pass_fail": True},
}


