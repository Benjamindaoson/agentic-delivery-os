"""
QueryTransformationAgent: deterministic query rewrite diff.
"""
from typing import Dict, Any, List


class QueryTransformationAgent:
    def __init__(self):
        self.agent_id = "query_transformation"
        self.agent_version = "1.0.0"

    def rewrite(self, query_payload: Dict[str, Any]) -> Dict[str, Any]:
        original = query_payload.get("original_query", "")
        rewritten = original.strip()
        rewrite_diff: List[Dict[str, str]] = []
        justification: List[str] = []

        if rewritten and not rewritten.endswith("?"):
            rewritten = f"{rewritten}?"
            rewrite_diff.append({"type": "ADD", "content": "terminal_question_mark"})
            justification.append("STRUCTURE_ALIGNMENT")

        if "please" in rewritten.lower():
            rewritten = rewritten.replace("please", "").strip()
            rewrite_diff.append({"type": "REMOVE", "content": "politeness_token"})
            justification.append("DISAMBIGUATION")

        return {
            "original_query": original,
            "rewritten_query": rewritten,
            "rewrite_diff": rewrite_diff,
            "rewrite_justification": justification or ["NO_CHANGE"],
            "confidence": 0.8 if rewrite_diff else 1.0,
            "reason_codes": justification or ["UNCHANGED"],
        }


