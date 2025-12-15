"""
IntentUnderstandingAgent: structured intent evaluation without execution.
"""
from typing import Dict, Any, List


class IntentUnderstandingAgent:
    def __init__(self):
        self.agent_id = "intent_understanding"
        self.agent_version = "1.0.0"

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        user_input = (payload.get("user_input") or "").strip().lower()
        history = payload.get("history_summary") or ""
        delivery_spec = payload.get("delivery_spec") or {}
        intents: List[Dict[str, Any]] = []

        if "rag" in user_input or delivery_spec.get("dataSourceType") == "rag":
            intents.append({"intent_id": "build_rag_pipeline", "confidence": 0.9, "description": "Construct RAG pipeline"})
        else:
            intents.append({"intent_id": "general_information", "confidence": 0.6, "description": "General knowledge retrieval"})

        if "update" in user_input:
            intents.append({"intent_id": "update_existing_system", "confidence": 0.5, "description": "Update existing delivery"})

        risk_flags = []
        if not user_input:
            risk_flags.append("AMBIGUOUS_GOAL")
        if history and len(history) > 500:
            risk_flags.append("SCOPE_OVERLAP")

        uncertainty = "LOW" if len(risk_flags) == 0 else ("MEDIUM" if len(risk_flags) == 1 else "HIGH")
        recommendation = "PROCEED"
        if "AMBIGUOUS_GOAL" in risk_flags:
            recommendation = "CLARIFY"

        return {
            "intent_candidates": intents,
            "intent_uncertainty_level": uncertainty,
            "risk_flags": risk_flags,
            "recommendation": recommendation,
            "reason_codes": ["INPUT_EMPTY"] if not user_input else ["SPEC_ANALYZED"],
        }


