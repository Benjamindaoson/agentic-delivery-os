"""
Quality Scorer - Automatic quality assessment
L5 Core Component: Evaluation & Metrics
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os


class QualityScore(BaseModel):
    """Comprehensive quality assessment"""
    run_id: str
    groundedness_score: float  # 0-1: How well grounded in evidence
    correctness_score: float  # 0-1: Factual correctness
    consistency_score: float  # 0-1: Internal consistency
    completeness_score: float  # 0-1: Addresses all aspects of query
    overall_score: float  # Weighted average
    assessment_method: str  # rule_based | llm_judge | hybrid
    confidence: float  # 0-1: Confidence in assessment
    details: Dict[str, Any]
    assessed_at: datetime = Field(default_factory=datetime.now)


class QualityScorer:
    """
    Automatic quality assessment for generated outputs
    Uses combination of rules and heuristics (can be extended with LLM judge)
    """
    
    def __init__(
        self,
        artifacts_path: str = "artifacts/eval",
        weights: Optional[Dict[str, float]] = None
    ):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Default scoring weights
        self.weights = weights or {
            "groundedness": 0.35,
            "correctness": 0.30,
            "consistency": 0.20,
            "completeness": 0.15
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
    
    def score(
        self,
        run_id: str,
        output: str,
        query: str,
        evidence: List[Dict[str, Any]],
        method: str = "rule_based"
    ) -> QualityScore:
        """
        Score the quality of a generated output
        Args:
            run_id: Unique run identifier
            output: Generated output to score
            query: Original query
            evidence: Evidence used (documents, context, etc.)
            method: Scoring method (rule_based | llm_judge | hybrid)
        Returns:
            QualityScore with detailed breakdown
        """
        # 1. Groundedness Score
        groundedness = self._score_groundedness(output, evidence)
        
        # 2. Correctness Score
        correctness = self._score_correctness(output, evidence, method)
        
        # 3. Consistency Score
        consistency = self._score_consistency(output)
        
        # 4. Completeness Score
        completeness = self._score_completeness(output, query)
        
        # Compute overall score
        overall = (
            self.weights["groundedness"] * groundedness +
            self.weights["correctness"] * correctness +
            self.weights["consistency"] * consistency +
            self.weights["completeness"] * completeness
        )
        
        # Confidence based on evidence availability
        confidence = min(1.0, len(evidence) / 5) if evidence else 0.5
        
        score = QualityScore(
            run_id=run_id,
            groundedness_score=groundedness,
            correctness_score=correctness,
            consistency_score=consistency,
            completeness_score=completeness,
            overall_score=overall,
            assessment_method=method,
            confidence=confidence,
            details={
                "output_length": len(output),
                "query_length": len(query),
                "evidence_count": len(evidence),
                "weights_used": self.weights
            }
        )
        
        # Save score
        self._save_score(score)
        
        return score
    
    def _score_groundedness(self, output: str, evidence: List[Dict[str, Any]]) -> float:
        """
        Score how well the output is grounded in evidence
        Uses rule-based overlap detection
        """
        if not evidence:
            return 0.5  # No evidence to check against
        
        output_lower = output.lower()
        output_words = set(output_lower.split())
        
        # Extract text from evidence
        evidence_text = " ".join([
            str(doc.get("content", doc.get("text", "")))
            for doc in evidence
        ]).lower()
        evidence_words = set(evidence_text.split())
        
        if not evidence_words:
            return 0.5
        
        # Compute word overlap
        overlap = len(output_words & evidence_words)
        overlap_ratio = overlap / len(output_words) if output_words else 0
        
        # Check for explicit citations
        has_citations = any(marker in output for marker in ["[", "(", "according to"])
        citation_bonus = 0.2 if has_citations else 0
        
        score = min(1.0, overlap_ratio * 1.5 + citation_bonus)
        return score
    
    def _score_correctness(
        self,
        output: str,
        evidence: List[Dict[str, Any]],
        method: str
    ) -> float:
        """
        Score factual correctness
        Rule-based: checks for contradiction patterns
        LLM-judge: would use LLM to verify claims
        """
        if method == "llm_judge":
            # Placeholder for LLM judge
            # In production, would call LLM to verify claims
            return 0.85  # Simulated score
        
        # Rule-based correctness checks
        output_lower = output.lower()
        
        # Negative patterns (likely incorrect)
        negative_patterns = [
            "i don't know",
            "i cannot",
            "no information",
            "unclear",
            "uncertain"
        ]
        
        has_negative = any(pattern in output_lower for pattern in negative_patterns)
        
        if has_negative:
            return 0.4  # Low score if output admits uncertainty
        
        # Positive patterns (likely correct)
        positive_patterns = [
            "based on",
            "according to",
            "the document states",
            "evidence shows"
        ]
        
        has_positive = any(pattern in output_lower for pattern in positive_patterns)
        
        # Check for specific facts/numbers (suggests concrete information)
        has_numbers = any(c.isdigit() for c in output)
        has_proper_nouns = any(word[0].isupper() for word in output.split() if len(word) > 1)
        
        score = 0.6  # Base score
        if has_positive:
            score += 0.2
        if has_numbers:
            score += 0.1
        if has_proper_nouns:
            score += 0.1
        
        return min(1.0, score)
    
    def _score_consistency(self, output: str) -> float:
        """
        Score internal consistency
        Checks for contradictions within the output
        """
        # Simple heuristic: check for contradiction markers
        output_lower = output.lower()
        
        contradiction_markers = [
            "however",
            "but",
            "although",
            "on the other hand",
            "contradicts"
        ]
        
        # Count contradiction markers
        contradiction_count = sum(
            1 for marker in contradiction_markers if marker in output_lower
        )
        
        # Some contradictions are okay (nuanced reasoning)
        # Too many suggest inconsistency
        if contradiction_count == 0:
            return 1.0  # Fully consistent (no contradictions)
        elif contradiction_count <= 2:
            return 0.8  # Some nuance is okay
        else:
            return max(0.4, 1.0 - (contradiction_count * 0.15))  # Too many contradictions
    
    def _score_completeness(self, output: str, query: str) -> float:
        """
        Score whether output addresses all aspects of the query
        """
        query_lower = query.lower()
        output_lower = output.lower()
        
        # Extract key question words
        question_words = ["what", "why", "how", "when", "where", "who", "which"]
        query_question_words = [w for w in question_words if w in query_lower]
        
        # Check if output is substantive
        output_length_score = min(1.0, len(output.split()) / 50)  # At least 50 words for complete answer
        
        # Check if output addresses the query type
        if not query_question_words:
            # Declarative query
            return output_length_score
        
        # For question queries, check if answer is provided
        answer_indicators = [
            "is",
            "are",
            "can",
            "should",
            "because",
            "by",
            "through"
        ]
        
        has_answer = any(indicator in output_lower for indicator in answer_indicators)
        answer_score = 1.0 if has_answer else 0.5
        
        return (output_length_score + answer_score) / 2
    
    def _save_score(self, score: QualityScore):
        """Persist quality score to artifacts"""
        path = os.path.join(self.artifacts_path, f"{score.run_id}_scores.json")
        with open(path, 'w') as f:
            f.write(score.model_dump_json(indent=2))
    
    def load_score(self, run_id: str) -> Optional[QualityScore]:
        """Load existing quality score"""
        path = os.path.join(self.artifacts_path, f"{run_id}_scores.json")
        
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                return QualityScore(**data)
        
        return None


# Singleton instance
_scorer = None

def get_scorer(weights: Optional[Dict[str, float]] = None) -> QualityScorer:
    """Get singleton QualityScorer instance"""
    global _scorer
    if _scorer is None:
        _scorer = QualityScorer(weights=weights)
    return _scorer



