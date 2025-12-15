"""
CandidateRankingAgent: compare candidates deterministically.
"""
from typing import List, Dict, Any


class CandidateRankingAgent:
    def __init__(self):
        self.agent_id = "candidate_ranking"
        self.agent_version = "1.0.0"

    def rank(self, candidates: List[Dict[str, Any]], preference: Dict[str, Any]) -> Dict[str, Any]:
        if not candidates:
            candidates = [
                {"candidate_id": "baseline", "cost": 1.0, "risk": 0.3, "quality": 0.7},
                {"candidate_id": "enhanced", "cost": 1.3, "risk": 0.4, "quality": 0.9},
            ]
        weight_cost = preference.get("cost_priority", 0.33)
        weight_risk = preference.get("risk_priority", 0.33)
        weight_quality = preference.get("quality_priority", 0.34)

        ranked = []
        elimination = {}
        for candidate in candidates:
            cost = candidate.get("cost", 1.0)
            risk = candidate.get("risk", 0.5)
            quality = candidate.get("quality", 0.5)
            score = weight_quality * quality - weight_cost * cost - weight_risk * risk
            pros = []
            cons = []
            if quality >= 0.8:
                pros.append("HIGH_QUALITY")
            if cost > 1.2:
                cons.append("HIGH_COST")
            ranked.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "score": score,
                    "pros": pros,
                    "cons": cons,
                }
            )
        ranked.sort(key=lambda x: x["score"], reverse=True)
        for idx, item in enumerate(ranked, start=1):
            item["rank"] = idx
            if item["cons"]:
                elimination[item["candidate_id"]] = item["cons"]

        return {
            "ranked_candidates": ranked,
            "elimination_reasons": elimination,
            "selection_confidence": 0.7,
            "reason_codes": ["MULTI_CRITERIA_SORT"],
        }


