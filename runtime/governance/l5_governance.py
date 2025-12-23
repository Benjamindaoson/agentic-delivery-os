import re
from typing import Dict, Any, List
from pydantic import BaseModel

class AccessDecision(BaseModel):
    allowed: bool
    reason: str

class GovernanceController:
    def __init__(self, cost_limit: float = 100.0):
        self.cumulative_cost = 0.0
        self.cost_limit = cost_limit

    def check_access(self, agent_id: str, tool_id: str) -> AccessDecision:
        # Placeholder for real ACL
        return AccessDecision(allowed=True, reason="Permitted")

    def check_injection(self, prompt: str) -> bool:
        injection_patterns = [
            r"ignore previous instructions",
            r"system prompt:",
            r"you are now a"
        ]
        for pattern in injection_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return True
        return False

    def check_cost_guardrail(self, session_cost: float) -> bool:
        return session_cost < self.cost_limit



