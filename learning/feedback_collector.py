"""
Feedback Collector - Unified feedback from multiple sources
L5 Core Component: Learning & Optimization (L5 GATE)
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
import json
import os
import uuid


class FeedbackItem(BaseModel):
    """Single piece of feedback"""
    feedback_id: str
    run_id: str
    source: Literal["auto_eval", "human", "system", "downstream"]
    feedback_type: Literal["quality", "correctness", "cost", "latency", "preference"]
    score: Optional[float] = None  # 0-1 if numeric
    label: Optional[str] = None  # accept | reject | edit | other
    comments: Optional[str] = None
    metadata: Dict[str, Any] = {}
    collected_at: datetime = Field(default_factory=datetime.now)


class FeedbackBatch(BaseModel):
    """Batch of feedback for analysis"""
    batch_id: str
    feedback_items: List[FeedbackItem]
    aggregated_stats: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)


class FeedbackCollector:
    """
    Collects feedback from multiple sources
    Enables learning from both automatic and human feedback
    """
    
    def __init__(self, feedback_path: str = "artifacts/learning/feedback"):
        self.feedback_path = feedback_path
        os.makedirs(feedback_path, exist_ok=True)
        
        # In-memory buffer for batching
        self.buffer: List[FeedbackItem] = []
        self.buffer_size = 10  # Flush after 10 items
    
    def collect_auto_eval_feedback(
        self,
        run_id: str,
        quality_score: float,
        cost: float,
        latency_ms: float,
        passed: bool
    ):
        """Collect feedback from automatic evaluation"""
        feedback = FeedbackItem(
            feedback_id=f"auto_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            source="auto_eval",
            feedback_type="quality",
            score=quality_score,
            label="accept" if passed else "reject",
            metadata={
                "cost": cost,
                "latency_ms": latency_ms,
                "passed": passed
            }
        )
        
        self._add_to_buffer(feedback)
    
    def collect_human_feedback(
        self,
        run_id: str,
        label: str,
        score: Optional[float] = None,
        comments: Optional[str] = None
    ):
        """Collect feedback from human annotation"""
        feedback = FeedbackItem(
            feedback_id=f"human_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            source="human",
            feedback_type="preference",
            score=score,
            label=label,
            comments=comments,
            metadata={}
        )
        
        self._add_to_buffer(feedback)
    
    def collect_system_feedback(
        self,
        run_id: str,
        feedback_type: str,
        score: float,
        metadata: Dict[str, Any]
    ):
        """Collect feedback from system monitoring"""
        feedback = FeedbackItem(
            feedback_id=f"sys_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            source="system",
            feedback_type=feedback_type,  # type: ignore
            score=score,
            metadata=metadata
        )
        
        self._add_to_buffer(feedback)
    
    def collect_downstream_feedback(
        self,
        run_id: str,
        success: bool,
        metadata: Dict[str, Any]
    ):
        """Collect feedback from downstream systems"""
        feedback = FeedbackItem(
            feedback_id=f"down_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            source="downstream",
            feedback_type="quality",
            score=1.0 if success else 0.0,
            label="accept" if success else "reject",
            metadata=metadata
        )
        
        self._add_to_buffer(feedback)
    
    def _add_to_buffer(self, feedback: FeedbackItem):
        """Add feedback to buffer and flush if full"""
        self.buffer.append(feedback)
        
        # Save individual feedback
        self._save_feedback(feedback)
        
        # Flush buffer if full
        if len(self.buffer) >= self.buffer_size:
            self.flush_buffer()
    
    def flush_buffer(self):
        """Process and save buffered feedback"""
        if not self.buffer:
            return
        
        # Create batch
        batch = FeedbackBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:8]}",
            feedback_items=self.buffer.copy(),
            aggregated_stats=self._compute_batch_stats(self.buffer)
        )
        
        # Save batch
        self._save_batch(batch)
        
        # Clear buffer
        self.buffer.clear()
    
    def _compute_batch_stats(self, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Compute aggregated statistics for batch"""
        if not feedback_items:
            return {}
        
        # Count by source
        by_source = {}
        for item in feedback_items:
            by_source[item.source] = by_source.get(item.source, 0) + 1
        
        # Average scores
        scored_items = [item for item in feedback_items if item.score is not None]
        avg_score = sum(item.score for item in scored_items) / len(scored_items) if scored_items else 0
        
        # Acceptance rate
        labeled_items = [item for item in feedback_items if item.label is not None]
        accept_count = sum(1 for item in labeled_items if item.label == "accept")
        accept_rate = accept_count / len(labeled_items) if labeled_items else 0
        
        return {
            "total_items": len(feedback_items),
            "by_source": by_source,
            "avg_score": avg_score,
            "accept_rate": accept_rate,
            "time_range": {
                "start": min(item.collected_at for item in feedback_items).isoformat(),
                "end": max(item.collected_at for item in feedback_items).isoformat()
            }
        }
    
    def _save_feedback(self, feedback: FeedbackItem):
        """Save individual feedback item"""
        path = os.path.join(self.feedback_path, f"{feedback.feedback_id}.json")
        with open(path, 'w') as f:
            f.write(feedback.model_dump_json(indent=2))
    
    def _save_batch(self, batch: FeedbackBatch):
        """Save feedback batch"""
        path = os.path.join(self.feedback_path, f"{batch.batch_id}.json")
        with open(path, 'w') as f:
            f.write(batch.model_dump_json(indent=2))
    
    def get_feedback_for_run(self, run_id: str) -> List[FeedbackItem]:
        """Retrieve all feedback for a specific run"""
        feedback_items = []
        
        for filename in os.listdir(self.feedback_path):
            if not filename.endswith('.json') or filename.startswith('batch_'):
                continue
            
            path = os.path.join(self.feedback_path, filename)
            try:
                with open(path) as f:
                    data = json.load(f)
                    item = FeedbackItem(**data)
                    if item.run_id == run_id:
                        feedback_items.append(item)
            except:
                continue
        
        return feedback_items
    
    def get_recent_feedback(self, limit: int = 100) -> List[FeedbackItem]:
        """Get most recent feedback items"""
        feedback_items = []
        
        for filename in sorted(os.listdir(self.feedback_path), reverse=True):
            if not filename.endswith('.json') or filename.startswith('batch_'):
                continue
            
            if len(feedback_items) >= limit:
                break
            
            path = os.path.join(self.feedback_path, filename)
            try:
                with open(path) as f:
                    data = json.load(f)
                    feedback_items.append(FeedbackItem(**data))
            except:
                continue
        
        return feedback_items


# Singleton instance
_collector = None

def get_feedback_collector() -> FeedbackCollector:
    """Get singleton FeedbackCollector instance"""
    global _collector
    if _collector is None:
        _collector = FeedbackCollector()
    return _collector



