"""
DialogueStrategyAgent: manage cross-turn strategy mode.
"""
from typing import Dict, Any, List


class DialogueStrategyAgent:
    def __init__(self):
        self.agent_id = "dialogue_strategy"
        self.agent_version = "1.0.0"

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        history = context.get("history_summary", "")
        recent_status = context.get("recent_status", "success")
        cost_pressure = context.get("cost_pressure", 0.0)
        failure_count = context.get("failure_count", 0)

        if failure_count > 0 or recent_status == "failed":
            mode = "CONSERVATIVE"
            reasons: List[str] = ["PREVIOUS_FAILURE"]
        elif cost_pressure > 0.7:
            mode = "CONSERVATIVE"
            reasons = ["COST_PRESSURE"]
        elif history and len(history) > 800:
            mode = "BALANCED"
            reasons = ["HISTORY_COMPLEXITY"]
        else:
            mode = "AGGRESSIVE"
            reasons = ["SUCCESS_HISTORY"]

        allowed = ["PROCEED"]
        forbidden = []
        if mode == "CONSERVATIVE":
            allowed = ["LIMIT_SCOPE", "CLARIFY_MORE"]
            forbidden = ["EXPAND_SCOPE"]
        elif mode == "BALANCED":
            allowed = ["PROCEED", "CLARIFY_MORE"]
            forbidden = []
        else:
            allowed = ["PROCEED", "EXPAND_SCOPE"]
            forbidden = ["LIMIT_SCOPE"]

        return {
            "current_strategy_mode": mode,
            "strategy_reason": reasons,
            "allowed_actions": allowed,
            "forbidden_actions": forbidden,
            "reason_codes": reasons,
        }


