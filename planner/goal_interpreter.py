"""
Goal Interpreter - Converts user input into explicit Goal Object
L5 Core Component: Goal Understanding & Planning
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
import hashlib


class GoalObject(BaseModel):
    """Explicit, structured representation of user intent"""
    goal_id: str
    goal_type: str  # analyze | build | retrieve | audit | replay | qa | summarize
    primary_intent: str
    success_criteria: List[str]
    constraints: Dict[str, Any]
    risk_level: str  # low | medium | high | critical
    priority: int  # 1-5
    estimated_complexity: str  # simple | moderate | complex | expert
    required_capabilities: List[str]
    context_requirements: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)


class GoalInterpreter:
    """
    Transforms raw user queries into structured Goal Objects
    Core L5 capability: Explicit goal understanding before planning
    """
    
    def __init__(self, artifacts_path: str = "artifacts/goals"):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Goal type classification rules
        self.goal_patterns = {
            "retrieve": ["what is", "tell me about", "explain", "describe"],
            "analyze": ["compare", "analyze", "evaluate", "assess", "why"],
            "build": ["create", "generate", "build", "write", "make"],
            "audit": ["check", "verify", "validate", "review", "audit"],
            "replay": ["replay", "rerun", "reproduce"],
            "qa": ["how to", "can you", "is it possible"],
            "summarize": ["summarize", "brief", "overview", "tldr"]
        }
    
    def interpret(self, query: str, context: Optional[Dict[str, Any]] = None) -> GoalObject:
        """
        Main interpretation method
        Args:
            query: Raw user input
            context: Optional context (session history, user prefs, etc.)
        Returns:
            GoalObject with explicit structure
        """
        query_lower = query.lower()
        
        # 1. Classify goal type
        goal_type = self._classify_goal_type(query_lower)
        
        # 2. Extract success criteria
        success_criteria = self._extract_success_criteria(query, goal_type)
        
        # 3. Infer constraints
        constraints = self._infer_constraints(query, context)
        
        # 4. Assess risk level
        risk_level = self._assess_risk_level(goal_type, constraints)
        
        # 5. Determine priority
        priority = self._determine_priority(context)
        
        # 6. Estimate complexity
        complexity = self._estimate_complexity(query, goal_type)
        
        # 7. Identify required capabilities
        required_capabilities = self._identify_capabilities(goal_type, complexity)
        
        # 8. Define context requirements
        context_requirements = self._define_context_requirements(goal_type)
        
        # Create goal object
        goal_id = self._generate_goal_id(query)
        goal = GoalObject(
            goal_id=goal_id,
            goal_type=goal_type,
            primary_intent=query,
            success_criteria=success_criteria,
            constraints=constraints,
            risk_level=risk_level,
            priority=priority,
            estimated_complexity=complexity,
            required_capabilities=required_capabilities,
            context_requirements=context_requirements
        )
        
        # Persist goal
        self._save_goal(goal)
        
        return goal
    
    def _classify_goal_type(self, query_lower: str) -> str:
        """Classify goal type based on patterns"""
        for goal_type, patterns in self.goal_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return goal_type
        return "retrieve"  # Default fallback
    
    def _extract_success_criteria(self, query: str, goal_type: str) -> List[str]:
        """Define what success looks like for this goal"""
        base_criteria = ["Response is relevant to query", "No hallucinations"]
        
        type_specific = {
            "retrieve": ["Accurate information", "Proper citations"],
            "analyze": ["Comparison is complete", "Conclusions are justified"],
            "build": ["Output is functional", "Meets specifications"],
            "audit": ["All items checked", "Issues documented"],
            "qa": ["Question fully answered", "Actionable guidance provided"],
            "summarize": ["Key points covered", "Concise output"]
        }
        
        return base_criteria + type_specific.get(goal_type, [])
    
    def _infer_constraints(self, query: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Infer execution constraints"""
        constraints = {
            "max_cost": 1.0,  # Default: $1
            "max_latency_ms": 30000,  # Default: 30s
            "require_citations": True,
            "allow_external_api": False,
            "safety_level": "standard"
        }
        
        # Override from context if provided
        if context and "constraints" in context:
            constraints.update(context["constraints"])
        
        # Infer from query
        if "urgent" in query.lower() or "quick" in query.lower():
            constraints["max_latency_ms"] = 5000
        
        if "detailed" in query.lower() or "comprehensive" in query.lower():
            constraints["max_cost"] = 2.0
        
        return constraints
    
    def _assess_risk_level(self, goal_type: str, constraints: Dict[str, Any]) -> str:
        """Assess execution risk"""
        if goal_type in ["build", "audit"]:
            return "medium"
        
        if constraints.get("allow_external_api", False):
            return "high"
        
        return "low"
    
    def _determine_priority(self, context: Optional[Dict[str, Any]]) -> int:
        """Determine execution priority (1=highest, 5=lowest)"""
        if context and "priority" in context:
            return context["priority"]
        return 3  # Default: medium priority
    
    def _estimate_complexity(self, query: str, goal_type: str) -> str:
        """Estimate computational complexity"""
        word_count = len(query.split())
        
        if word_count < 5:
            return "simple"
        elif word_count < 15:
            return "moderate"
        elif word_count < 30:
            return "complex"
        else:
            return "expert"
    
    def _identify_capabilities(self, goal_type: str, complexity: str) -> List[str]:
        """Identify required system capabilities"""
        base_capabilities = ["reasoning", "retrieval"]
        
        type_capabilities = {
            "analyze": ["reasoning", "comparison", "retrieval"],
            "build": ["generation", "validation"],
            "audit": ["validation", "reasoning"],
            "summarize": ["generation", "abstraction"]
        }
        
        caps = type_capabilities.get(goal_type, base_capabilities)
        
        if complexity in ["complex", "expert"]:
            caps.append("multi_hop_reasoning")
        
        return caps
    
    def _define_context_requirements(self, goal_type: str) -> Dict[str, Any]:
        """Define what context is needed"""
        return {
            "require_history": goal_type in ["analyze", "audit"],
            "require_external_data": goal_type == "retrieve",
            "require_validation": goal_type in ["build", "audit"]
        }
    
    def _generate_goal_id(self, query: str) -> str:
        """Generate deterministic goal ID"""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"goal_{timestamp}_{query_hash}"
    
    def _save_goal(self, goal: GoalObject):
        """Persist goal to artifacts"""
        path = os.path.join(self.artifacts_path, f"{goal.goal_id}.json")
        with open(path, "w") as f:
            f.write(goal.model_dump_json(indent=2))


# Singleton instance
_interpreter = None

def get_interpreter() -> GoalInterpreter:
    """Get singleton GoalInterpreter instance"""
    global _interpreter
    if _interpreter is None:
        _interpreter = GoalInterpreter()
    return _interpreter



