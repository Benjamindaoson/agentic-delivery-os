"""
Generation Reranker - Rerank candidates based on multiple criteria
L5 Core Component: Intelligent candidate selection
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os


class RankingScore(BaseModel):
    """Detailed scoring breakdown"""
    evidence_coverage: float  # 0-1
    consistency: float  # 0-1
    cost_efficiency: float  # 0-1
    confidence: float  # 0-1
    total_score: float  # Weighted sum


class RankedCandidate(BaseModel):
    """Candidate with ranking information"""
    candidate_id: str
    content: str
    rank: int
    score: RankingScore
    rationale: str


class RerankerResult(BaseModel):
    """Result of reranking process"""
    request_id: str
    chosen_candidate: RankedCandidate
    rejected_candidates: List[RankedCandidate]
    selection_rationale: str
    reranking_strategy: str
    created_at: datetime = Field(default_factory=datetime.now)


class GenerationReranker:
    """
    Reranks generated candidates based on multiple criteria
    Ensures best candidate is selected
    """
    
    def __init__(
        self,
        artifacts_path: str = "artifacts/reranking",
        weights: Optional[Dict[str, float]] = None
    ):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Default weights for scoring
        self.weights = weights or {
            "evidence_coverage": 0.35,
            "consistency": 0.25,
            "cost_efficiency": 0.20,
            "confidence": 0.20
        }
        
        # Ensure weights sum to 1.0
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
    
    def rerank(
        self,
        candidates: List[Any],  # GenerationCandidate objects
        context: Dict[str, Any],
        strategy: str = "multi_criteria"
    ) -> RerankerResult:
        """
        Rerank candidates and select best one
        Args:
            candidates: List of GenerationCandidate objects
            context: Context including evidence, query, etc.
            strategy: Reranking strategy
        Returns:
            RerankerResult with chosen and rejected candidates
        """
        # Score all candidates
        scored_candidates = []
        
        for candidate in candidates:
            score = self._compute_score(candidate, context)
            
            ranked = RankedCandidate(
                candidate_id=candidate.candidate_id,
                content=candidate.content,
                rank=0,  # Will be assigned after sorting
                score=score,
                rationale=self._generate_rationale(score)
            )
            scored_candidates.append(ranked)
        
        # Sort by total score
        scored_candidates.sort(key=lambda x: x.score.total_score, reverse=True)
        
        # Assign ranks
        for i, candidate in enumerate(scored_candidates):
            candidate.rank = i + 1
        
        # Select best and separate rejected
        chosen = scored_candidates[0]
        rejected = scored_candidates[1:]
        
        # Generate selection rationale
        selection_rationale = self._generate_selection_rationale(chosen, rejected)
        
        result = RerankerResult(
            request_id=f"rerank_{chosen.candidate_id}",
            chosen_candidate=chosen,
            rejected_candidates=rejected,
            selection_rationale=selection_rationale,
            reranking_strategy=strategy
        )
        
        # Save result
        self._save_result(result)
        
        return result
    
    def _compute_score(self, candidate: Any, context: Dict[str, Any]) -> RankingScore:
        """Compute comprehensive score for a candidate"""
        # 1. Evidence Coverage Score
        evidence_coverage = self._score_evidence_coverage(candidate, context)
        
        # 2. Consistency Score
        consistency = self._score_consistency(candidate, context)
        
        # 3. Cost Efficiency Score
        cost_efficiency = self._score_cost_efficiency(candidate)
        
        # 4. Confidence Score
        confidence = self._score_confidence(candidate)
        
        # Compute weighted total
        total_score = (
            self.weights["evidence_coverage"] * evidence_coverage +
            self.weights["consistency"] * consistency +
            self.weights["cost_efficiency"] * cost_efficiency +
            self.weights["confidence"] * confidence
        )
        
        return RankingScore(
            evidence_coverage=evidence_coverage,
            consistency=consistency,
            cost_efficiency=cost_efficiency,
            confidence=confidence,
            total_score=total_score
        )
    
    def _score_evidence_coverage(self, candidate: Any, context: Dict[str, Any]) -> float:
        """Score based on evidence coverage"""
        # Simplified: check if candidate references context
        if "documents" not in context:
            return 0.5  # Default score if no documents
        
        doc_count = len(context.get("documents", []))
        content_lower = candidate.content.lower()
        
        # Simple heuristic: longer responses likely cover more evidence
        content_length_score = min(1.0, len(content_lower) / 200)
        
        # Check for citation markers (simplified)
        has_citations = "[" in content_lower or "based on" in content_lower
        citation_score = 1.0 if has_citations else 0.7
        
        return (content_length_score + citation_score) / 2
    
    def _score_consistency(self, candidate: Any, context: Dict[str, Any]) -> float:
        """Score based on consistency with evidence"""
        # Simplified consistency check
        # In production, would use semantic similarity or LLM judge
        
        # Check if candidate content contradicts obvious facts
        content_lower = candidate.content.lower()
        
        # Positive indicators
        has_reasoning = any(word in content_lower for word in ["because", "therefore", "since"])
        is_coherent = len(candidate.content.split()) > 10  # Not too short
        
        score = 0.6  # Base score
        if has_reasoning:
            score += 0.2
        if is_coherent:
            score += 0.2
        
        return min(1.0, score)
    
    def _score_cost_efficiency(self, candidate: Any) -> float:
        """Score based on cost efficiency"""
        # Normalize cost (assuming max reasonable cost is $0.10)
        max_cost = 0.10
        cost = candidate.estimated_cost
        
        # Lower cost = higher score
        cost_score = 1.0 - min(1.0, cost / max_cost)
        
        # Factor in quality
        quality = candidate.estimated_quality
        
        # Efficiency: quality per dollar
        if cost > 0:
            efficiency = quality / cost
            efficiency_score = min(1.0, efficiency / 50)  # Normalize
        else:
            efficiency_score = 1.0
        
        return (cost_score + efficiency_score) / 2
    
    def _score_confidence(self, candidate: Any) -> float:
        """Score based on model confidence"""
        # Use estimated quality as proxy for confidence
        return candidate.estimated_quality
    
    def _generate_rationale(self, score: RankingScore) -> str:
        """Generate human-readable rationale for score"""
        reasons = []
        
        if score.evidence_coverage > 0.8:
            reasons.append("Strong evidence coverage")
        elif score.evidence_coverage < 0.5:
            reasons.append("Weak evidence coverage")
        
        if score.consistency > 0.8:
            reasons.append("Highly consistent")
        elif score.consistency < 0.5:
            reasons.append("Consistency concerns")
        
        if score.cost_efficiency > 0.7:
            reasons.append("Cost-effective")
        
        if score.confidence > 0.8:
            reasons.append("High confidence")
        
        if not reasons:
            reasons.append("Moderate performance across all criteria")
        
        return "; ".join(reasons)
    
    def _generate_selection_rationale(
        self,
        chosen: RankedCandidate,
        rejected: List[RankedCandidate]
    ) -> str:
        """Generate rationale for final selection"""
        rationale_parts = [
            f"Selected candidate {chosen.candidate_id} with score {chosen.score.total_score:.3f}."
        ]
        
        # Highlight why chosen is better
        if rejected:
            best_rejected = rejected[0]
            score_diff = chosen.score.total_score - best_rejected.score.total_score
            rationale_parts.append(
                f"Outperformed next best by {score_diff:.3f} points."
            )
            
            # Mention key strengths
            if chosen.score.evidence_coverage > best_rejected.score.evidence_coverage:
                rationale_parts.append("Superior evidence coverage.")
            
            if chosen.score.cost_efficiency > best_rejected.score.cost_efficiency:
                rationale_parts.append("Better cost efficiency.")
        
        rationale_parts.append(f"Rationale: {chosen.rationale}")
        
        return " ".join(rationale_parts)
    
    def _save_result(self, result: RerankerResult):
        """Save reranking result to artifacts"""
        path = os.path.join(self.artifacts_path, f"{result.request_id}.json")
        with open(path, 'w') as f:
            f.write(result.model_dump_json(indent=2))


# Singleton instance
_reranker = None

def get_reranker(weights: Optional[Dict[str, float]] = None) -> GenerationReranker:
    """Get singleton GenerationReranker instance"""
    global _reranker
    if _reranker is None:
        _reranker = GenerationReranker(weights=weights)
    return _reranker



