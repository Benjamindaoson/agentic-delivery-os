"""
Policy Updater - Update strategies based on feedback
L5 Core Component: Learning closed-loop (L5 GATE)
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
from collections import defaultdict


class PolicyUpdate(BaseModel):
    """Single policy update record"""
    update_id: str
    policy_type: str  # planner | tool_selection | agent_routing | generation
    previous_version: str
    new_version: str
    trigger: str  # feedback_threshold | manual | scheduled | regression
    changes: Dict[str, Any]
    metrics_before: Dict[str, float]
    metrics_after: Optional[Dict[str, float]] = None
    approved: bool = False
    rolled_back: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


class PolicyUpdateResult(BaseModel):
    """Result of policy update operation"""
    success: bool
    updates_applied: List[PolicyUpdate]
    validation_passed: bool
    rollback_triggered: bool = False
    message: str


class PolicyUpdater:
    """
    Updates system policies based on accumulated feedback
    Core L5 Learning Component - enables strategy evolution
    """
    
    def __init__(
        self,
        updates_path: str = "artifacts/learning/policy_updates",
        update_threshold: int = 20  # Minimum feedback items before update
    ):
        self.updates_path = updates_path
        self.update_threshold = update_threshold
        os.makedirs(updates_path, exist_ok=True)
        
        # Track update history
        self.update_history: List[PolicyUpdate] = []
    
    def analyze_and_update(
        self,
        feedback_items: List[Any],  # FeedbackItem objects
        current_policies: Dict[str, Any]
    ) -> PolicyUpdateResult:
        """
        Analyze feedback and update policies if needed
        Args:
            feedback_items: Accumulated feedback
            current_policies: Current policy configurations
        Returns:
            PolicyUpdateResult with updates applied
        """
        if len(feedback_items) < self.update_threshold:
            return PolicyUpdateResult(
                success=False,
                updates_applied=[],
                validation_passed=False,
                message=f"Need {self.update_threshold - len(feedback_items)} more feedback items"
            )
        
        # Analyze feedback by policy type
        updates = []
        
        # 1. Analyze planner strategy feedback
        planner_update = self._analyze_planner_feedback(feedback_items, current_policies)
        if planner_update:
            updates.append(planner_update)
        
        # 2. Analyze tool selection feedback
        tool_update = self._analyze_tool_feedback(feedback_items, current_policies)
        if tool_update:
            updates.append(tool_update)
        
        # 3. Analyze agent routing feedback
        agent_update = self._analyze_agent_feedback(feedback_items, current_policies)
        if agent_update:
            updates.append(agent_update)
        
        # 4. Analyze generation parameters
        gen_update = self._analyze_generation_feedback(feedback_items, current_policies)
        if gen_update:
            updates.append(gen_update)
        
        # Validate updates
        validation_passed = self._validate_updates(updates)
        
        if validation_passed:
            # Apply updates
            self._apply_updates(updates)
            
            # Save update records
            for update in updates:
                self._save_update(update)
            
            return PolicyUpdateResult(
                success=True,
                updates_applied=updates,
                validation_passed=True,
                message=f"Applied {len(updates)} policy updates"
            )
        else:
            return PolicyUpdateResult(
                success=False,
                updates_applied=[],
                validation_passed=False,
                message="Update validation failed"
            )
    
    def _analyze_planner_feedback(
        self,
        feedback_items: List[Any],
        current_policies: Dict[str, Any]
    ) -> Optional[PolicyUpdate]:
        """Analyze feedback for planner strategy updates"""
        # Group feedback by goal type
        by_goal_type = defaultdict(list)
        for item in feedback_items:
            goal_type = item.metadata.get("goal_type", "unknown")
            if item.score is not None:
                by_goal_type[goal_type].append(item.score)
        
        # Check if any goal type has consistently low scores
        updates_needed = {}
        for goal_type, scores in by_goal_type.items():
            if len(scores) >= 5:
                avg_score = sum(scores) / len(scores)
                if avg_score < 0.7:  # Threshold for poor performance
                    # Suggest strategy change
                    current_strategy = current_policies.get("planner", {}).get(goal_type, "default")
                    # Simple heuristic: rotate strategies
                    strategies = ["sequential", "parallel", "hierarchical"]
                    current_idx = strategies.index(current_strategy) if current_strategy in strategies else 0
                    new_strategy = strategies[(current_idx + 1) % len(strategies)]
                    updates_needed[goal_type] = new_strategy
        
        if updates_needed:
            import uuid
            return PolicyUpdate(
                update_id=f"planner_{uuid.uuid4().hex[:8]}",
                policy_type="planner",
                previous_version=current_policies.get("planner_version", "1.0"),
                new_version=f"{float(current_policies.get('planner_version', '1.0')) + 0.1:.1f}",
                trigger="feedback_threshold",
                changes=updates_needed,
                metrics_before={
                    "avg_score_by_goal": {gt: sum(s)/len(s) for gt, s in by_goal_type.items()}
                }
            )
        
        return None
    
    def _analyze_tool_feedback(
        self,
        feedback_items: List[Any],
        current_policies: Dict[str, Any]
    ) -> Optional[PolicyUpdate]:
        """Analyze feedback for tool selection updates"""
        # Extract tool performance from metadata
        tool_scores = defaultdict(list)
        for item in feedback_items:
            tools_used = item.metadata.get("tools_used", [])
            if item.score is not None:
                for tool in tools_used:
                    tool_scores[tool].append(item.score)
        
        # Identify underperforming tools
        tool_preferences = {}
        for tool, scores in tool_scores.items():
            if len(scores) >= 3:
                avg_score = sum(scores) / len(scores)
                # Adjust tool weight based on performance
                tool_preferences[tool] = {
                    "weight": max(0.1, avg_score),  # Lower bound 0.1
                    "avg_score": avg_score,
                    "sample_size": len(scores)
                }
        
        if tool_preferences:
            import uuid
            return PolicyUpdate(
                update_id=f"tools_{uuid.uuid4().hex[:8]}",
                policy_type="tool_selection",
                previous_version=current_policies.get("tool_version", "1.0"),
                new_version=f"{float(current_policies.get('tool_version', '1.0')) + 0.1:.1f}",
                trigger="feedback_threshold",
                changes={"tool_preferences": tool_preferences},
                metrics_before={"tool_count": len(tool_scores)}
            )
        
        return None
    
    def _analyze_agent_feedback(
        self,
        feedback_items: List[Any],
        current_policies: Dict[str, Any]
    ) -> Optional[PolicyUpdate]:
        """Analyze feedback for agent routing updates"""
        # Extract agent performance
        agent_scores = defaultdict(list)
        for item in feedback_items:
            agent_id = item.metadata.get("agent_id")
            if agent_id and item.score is not None:
                agent_scores[agent_id].append(item.score)
        
        # Compute agent priorities
        agent_routing = {}
        for agent_id, scores in agent_scores.items():
            if len(scores) >= 3:
                avg_score = sum(scores) / len(scores)
                agent_routing[agent_id] = {
                    "priority": int(avg_score * 100),  # 0-100
                    "enabled": avg_score > 0.5,
                    "avg_score": avg_score
                }
        
        if agent_routing:
            import uuid
            return PolicyUpdate(
                update_id=f"agent_{uuid.uuid4().hex[:8]}",
                policy_type="agent_routing",
                previous_version=current_policies.get("agent_version", "1.0"),
                new_version=f"{float(current_policies.get('agent_version', '1.0')) + 0.1:.1f}",
                trigger="feedback_threshold",
                changes={"agent_routing": agent_routing},
                metrics_before={"agent_count": len(agent_scores)}
            )
        
        return None
    
    def _analyze_generation_feedback(
        self,
        feedback_items: List[Any],
        current_policies: Dict[str, Any]
    ) -> Optional[PolicyUpdate]:
        """Analyze feedback for generation parameter updates"""
        # Extract generation metrics
        cost_scores = []
        quality_scores = []
        
        for item in feedback_items:
            if item.feedback_type == "quality" and item.score is not None:
                quality_scores.append(item.score)
            cost = item.metadata.get("cost")
            if cost is not None and item.score is not None:
                cost_scores.append((cost, item.score))
        
        # Optimize cost-quality tradeoff
        if cost_scores and len(cost_scores) >= 5:
            # Simple heuristic: find optimal cost point
            avg_quality = sum(q for _, q in cost_scores) / len(cost_scores)
            avg_cost = sum(c for c, _ in cost_scores) / len(cost_scores)
            
            # Adjust generation parameters
            changes = {
                "target_quality": avg_quality,
                "max_cost": avg_cost * 1.2,  # 20% buffer
                "num_candidates": 3 if avg_quality < 0.8 else 2  # More candidates if quality is low
            }
            
            import uuid
            return PolicyUpdate(
                update_id=f"gen_{uuid.uuid4().hex[:8]}",
                policy_type="generation",
                previous_version=current_policies.get("generation_version", "1.0"),
                new_version=f"{float(current_policies.get('generation_version', '1.0')) + 0.1:.1f}",
                trigger="feedback_threshold",
                changes=changes,
                metrics_before={
                    "avg_quality": avg_quality,
                    "avg_cost": avg_cost
                }
            )
        
        return None
    
    def _validate_updates(self, updates: List[PolicyUpdate]) -> bool:
        """Validate proposed updates"""
        # Simple validation rules
        for update in updates:
            # Check version progression
            try:
                prev_ver = float(update.previous_version)
                new_ver = float(update.new_version)
                if new_ver <= prev_ver:
                    return False
            except:
                pass
            
            # Check changes are non-empty
            if not update.changes:
                return False
        
        return True
    
    def _apply_updates(self, updates: List[PolicyUpdate]):
        """Apply validated updates"""
        # Mark as approved
        for update in updates:
            update.approved = True
            self.update_history.append(update)
    
    def _save_update(self, update: PolicyUpdate):
        """Persist update record"""
        path = os.path.join(self.updates_path, f"{update.update_id}.json")
        with open(path, 'w') as f:
            f.write(update.model_dump_json(indent=2))
    
    def rollback_update(self, update_id: str) -> bool:
        """Rollback a specific update"""
        for update in self.update_history:
            if update.update_id == update_id:
                update.rolled_back = True
                self._save_update(update)
                return True
        return False
    
    def get_update_history(self, policy_type: Optional[str] = None) -> List[PolicyUpdate]:
        """Get update history, optionally filtered by type"""
        if policy_type:
            return [u for u in self.update_history if u.policy_type == policy_type]
        return self.update_history


# Singleton instance
_updater = None

def get_policy_updater() -> PolicyUpdater:
    """Get singleton PolicyUpdater instance"""
    global _updater
    if _updater is None:
        _updater = PolicyUpdater()
    return _updater



