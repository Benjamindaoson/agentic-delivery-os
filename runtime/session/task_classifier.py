"""
Task Type Classifier: Explicit task type classification for routing.
Outputs task_type.json artifacts for replay and policy selection.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class TaskType(str, Enum):
    """Supported task types."""
    RAG_QA = "rag_qa"  # Question answering with RAG
    RAG_SUMMARY = "rag_summary"  # Summarization with RAG
    TRANSFORM = "transform"  # Data transformation
    GENERATE = "generate"  # Content generation
    ANALYZE = "analyze"  # Analysis task
    VALIDATE = "validate"  # Validation task
    DECIDE = "decide"  # Decision making
    EXPLORE = "explore"  # Exploration/research
    CHAT = "chat"  # Conversational
    UNKNOWN = "unknown"


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"  # Single step, direct answer
    MODERATE = "moderate"  # Few steps, some reasoning
    COMPLEX = "complex"  # Multiple steps, planning needed
    EXPERT = "expert"  # Deep reasoning, multi-agent


@dataclass
class TaskClassification:
    """Task classification result."""
    run_id: str
    
    # Classification
    task_type: TaskType
    task_complexity: TaskComplexity
    confidence: float  # 0.0-1.0
    
    # Features used
    features: Dict[str, Any] = field(default_factory=dict)
    
    # Routing hints
    recommended_plan: str = "default"
    recommended_agents: List[str] = field(default_factory=list)
    recommended_tools: List[str] = field(default_factory=list)
    
    # Constraints inferred
    estimated_cost_range: tuple = (0.01, 0.10)
    estimated_latency_ms: int = 5000
    requires_retrieval: bool = True
    requires_generation: bool = True
    
    # Metadata
    classified_at: str = ""
    classifier_version: str = "1.0"
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.classified_at:
            self.classified_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_type": self.task_type.value,
            "task_complexity": self.task_complexity.value,
            "confidence": self.confidence,
            "features": self.features,
            "recommended_plan": self.recommended_plan,
            "recommended_agents": self.recommended_agents,
            "recommended_tools": self.recommended_tools,
            "estimated_cost_range": list(self.estimated_cost_range),
            "estimated_latency_ms": self.estimated_latency_ms,
            "requires_retrieval": self.requires_retrieval,
            "requires_generation": self.requires_generation,
            "classified_at": self.classified_at,
            "classifier_version": self.classifier_version,
            "schema_version": self.schema_version
        }


class TaskClassifier:
    """
    Classifies incoming tasks into types for routing.
    
    Features:
    - Explicit task type output
    - Artifact-based (replayable)
    - Used by planner, agent, and tool policy selection
    """
    
    # Task type patterns
    TYPE_PATTERNS = {
        TaskType.RAG_QA: [
            "what is", "who is", "when did", "where is", "why did",
            "how does", "explain", "describe", "tell me about"
        ],
        TaskType.RAG_SUMMARY: [
            "summarize", "summary", "brief", "overview", "key points",
            "tldr", "main ideas"
        ],
        TaskType.TRANSFORM: [
            "convert", "transform", "change", "translate", "reformat",
            "parse", "extract"
        ],
        TaskType.GENERATE: [
            "write", "create", "generate", "compose", "draft",
            "make", "build"
        ],
        TaskType.ANALYZE: [
            "analyze", "compare", "evaluate", "assess", "examine",
            "review", "investigate"
        ],
        TaskType.VALIDATE: [
            "validate", "verify", "check", "confirm", "test",
            "is it correct", "is this right"
        ],
        TaskType.DECIDE: [
            "should i", "should we", "decide", "choose", "recommend",
            "which is better", "pros and cons"
        ],
        TaskType.EXPLORE: [
            "find", "search", "discover", "explore", "research",
            "look for", "identify"
        ],
        TaskType.CHAT: [
            "hello", "hi", "hey", "thanks", "thank you",
            "bye", "goodbye"
        ]
    }
    
    # Complexity indicators
    COMPLEXITY_INDICATORS = {
        TaskComplexity.SIMPLE: {
            "max_words": 10,
            "indicators": ["quick", "simple", "just", "only"]
        },
        TaskComplexity.MODERATE: {
            "max_words": 30,
            "indicators": ["also", "and then", "including"]
        },
        TaskComplexity.COMPLEX: {
            "max_words": 100,
            "indicators": ["step by step", "comprehensive", "detailed", "multiple"]
        },
        TaskComplexity.EXPERT: {
            "max_words": float("inf"),
            "indicators": ["in-depth", "expert", "advanced", "complete analysis"]
        }
    }
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.task_type_dir = os.path.join(artifacts_dir, "task_type")
        os.makedirs(self.task_type_dir, exist_ok=True)
    
    def classify(
        self,
        run_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskClassification:
        """
        Classify a task.
        
        Args:
            run_id: Run identifier
            query: Task query
            context: Optional context
            
        Returns:
            TaskClassification
        """
        context = context or {}
        query_lower = query.lower()
        
        # Extract features
        features = self._extract_features(query, context)
        
        # Classify type
        task_type, type_confidence = self._classify_type(query_lower, features)
        
        # Classify complexity
        complexity = self._classify_complexity(query, features)
        
        # Generate recommendations
        recommended_plan = self._recommend_plan(task_type, complexity)
        recommended_agents = self._recommend_agents(task_type)
        recommended_tools = self._recommend_tools(task_type)
        
        # Estimate resources
        cost_range = self._estimate_cost(task_type, complexity)
        latency = self._estimate_latency(task_type, complexity)
        
        classification = TaskClassification(
            run_id=run_id,
            task_type=task_type,
            task_complexity=complexity,
            confidence=type_confidence,
            features=features,
            recommended_plan=recommended_plan,
            recommended_agents=recommended_agents,
            recommended_tools=recommended_tools,
            estimated_cost_range=cost_range,
            estimated_latency_ms=latency,
            requires_retrieval=task_type in [
                TaskType.RAG_QA, TaskType.RAG_SUMMARY, TaskType.EXPLORE
            ],
            requires_generation=task_type in [
                TaskType.RAG_QA, TaskType.RAG_SUMMARY, TaskType.GENERATE,
                TaskType.ANALYZE, TaskType.DECIDE
            ]
        )
        
        # Save artifact
        self._save_classification(classification)
        
        return classification
    
    def load_classification(self, run_id: str) -> Optional[TaskClassification]:
        """Load classification from artifact."""
        path = os.path.join(self.task_type_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return TaskClassification(
            run_id=data["run_id"],
            task_type=TaskType(data["task_type"]),
            task_complexity=TaskComplexity(data["task_complexity"]),
            confidence=data["confidence"],
            features=data.get("features", {}),
            recommended_plan=data.get("recommended_plan", "default"),
            recommended_agents=data.get("recommended_agents", []),
            recommended_tools=data.get("recommended_tools", []),
            estimated_cost_range=tuple(data.get("estimated_cost_range", [0.01, 0.10])),
            estimated_latency_ms=data.get("estimated_latency_ms", 5000),
            requires_retrieval=data.get("requires_retrieval", True),
            requires_generation=data.get("requires_generation", True),
            classified_at=data.get("classified_at", ""),
            classifier_version=data.get("classifier_version", "1.0"),
            schema_version=data.get("schema_version", "1.0")
        )
    
    def _extract_features(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features from query and context."""
        words = query.split()
        
        return {
            "query_length": len(query),
            "word_count": len(words),
            "has_question_mark": "?" in query,
            "has_code": "```" in query or "def " in query,
            "has_url": "http" in query.lower(),
            "has_numbers": any(c.isdigit() for c in query),
            "context_provided": bool(context),
            "session_context": context.get("session_id") is not None
        }
    
    def _classify_type(
        self,
        query_lower: str,
        features: Dict[str, Any]
    ) -> tuple:
        """Classify task type."""
        scores: Dict[TaskType, float] = {t: 0.0 for t in TaskType}
        
        for task_type, patterns in self.TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    scores[task_type] += 1.0
        
        # Boost based on features
        if features.get("has_question_mark"):
            scores[TaskType.RAG_QA] += 0.5
        
        if features.get("has_code"):
            scores[TaskType.TRANSFORM] += 0.3
            scores[TaskType.ANALYZE] += 0.3
        
        # Find best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        if best_score == 0:
            return TaskType.UNKNOWN, 0.5
        
        # Calculate confidence
        total_score = sum(scores.values())
        confidence = best_score / total_score if total_score > 0 else 0.5
        
        return best_type, min(0.95, confidence)
    
    def _classify_complexity(
        self,
        query: str,
        features: Dict[str, Any]
    ) -> TaskComplexity:
        """Classify task complexity."""
        word_count = features.get("word_count", 0)
        query_lower = query.lower()
        
        for complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE, TaskComplexity.COMPLEX]:
            indicators = self.COMPLEXITY_INDICATORS[complexity]
            
            # Check word count
            if word_count <= indicators["max_words"]:
                # Check for indicators
                for indicator in indicators["indicators"]:
                    if indicator in query_lower:
                        return complexity
                
                # Default based on word count
                if complexity == TaskComplexity.SIMPLE and word_count <= 10:
                    return complexity
                if complexity == TaskComplexity.MODERATE and word_count <= 30:
                    return complexity
        
        return TaskComplexity.COMPLEX
    
    def _recommend_plan(
        self,
        task_type: TaskType,
        complexity: TaskComplexity
    ) -> str:
        """Recommend execution plan."""
        if task_type == TaskType.CHAT:
            return "direct_response"
        if complexity == TaskComplexity.SIMPLE:
            return "simple_rag"
        if complexity == TaskComplexity.MODERATE:
            return "standard_rag"
        if complexity == TaskComplexity.COMPLEX:
            return "multi_step_rag"
        return "expert_analysis"
    
    def _recommend_agents(self, task_type: TaskType) -> List[str]:
        """Recommend agents for task type."""
        base_agents = ["orchestrator_agent"]
        
        if task_type in [TaskType.RAG_QA, TaskType.RAG_SUMMARY, TaskType.EXPLORE]:
            base_agents.extend(["data_agent", "execution_agent"])
        if task_type in [TaskType.GENERATE, TaskType.ANALYZE]:
            base_agents.extend(["execution_agent", "evaluation_agent"])
        if task_type == TaskType.DECIDE:
            base_agents.extend(["data_agent", "evaluation_agent"])
        
        return base_agents
    
    def _recommend_tools(self, task_type: TaskType) -> List[str]:
        """Recommend tools for task type."""
        if task_type in [TaskType.RAG_QA, TaskType.RAG_SUMMARY]:
            return ["retriever", "embedder", "reranker", "llm_generator"]
        if task_type == TaskType.TRANSFORM:
            return ["parser", "transformer", "formatter"]
        if task_type == TaskType.GENERATE:
            return ["llm_generator", "validator"]
        if task_type == TaskType.ANALYZE:
            return ["retriever", "analyzer", "llm_generator"]
        return ["llm_generator"]
    
    def _estimate_cost(
        self,
        task_type: TaskType,
        complexity: TaskComplexity
    ) -> tuple:
        """Estimate cost range."""
        base_costs = {
            TaskComplexity.SIMPLE: (0.005, 0.02),
            TaskComplexity.MODERATE: (0.02, 0.08),
            TaskComplexity.COMPLEX: (0.08, 0.25),
            TaskComplexity.EXPERT: (0.25, 1.0)
        }
        
        base = base_costs.get(complexity, (0.02, 0.08))
        
        # Adjust for task type
        if task_type == TaskType.CHAT:
            return (0.001, 0.01)
        if task_type in [TaskType.EXPLORE, TaskType.ANALYZE]:
            return (base[0] * 1.5, base[1] * 1.5)
        
        return base
    
    def _estimate_latency(
        self,
        task_type: TaskType,
        complexity: TaskComplexity
    ) -> int:
        """Estimate latency in ms."""
        base_latencies = {
            TaskComplexity.SIMPLE: 2000,
            TaskComplexity.MODERATE: 5000,
            TaskComplexity.COMPLEX: 15000,
            TaskComplexity.EXPERT: 60000
        }
        
        base = base_latencies.get(complexity, 5000)
        
        if task_type == TaskType.CHAT:
            return 1000
        if task_type in [TaskType.EXPLORE, TaskType.ANALYZE]:
            return int(base * 1.5)
        
        return base
    
    def _save_classification(self, classification: TaskClassification) -> None:
        """Save classification to artifact."""
        path = os.path.join(self.task_type_dir, f"{classification.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(classification.to_dict(), f, indent=2, ensure_ascii=False)

