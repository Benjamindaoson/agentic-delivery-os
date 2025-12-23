"""
Task Type Classifier: Explicit task classification for downstream routing.
Outputs task_type.json artifact for replay and policy selection.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class TaskType(str, Enum):
    """Primary task types."""
    RAG_QA = "rag_qa"  # Question answering with retrieval
    RAG_SUMMARY = "rag_summary"  # Summarization with retrieval
    TRANSFORM = "transform"  # Data transformation
    GENERATE = "generate"  # Content generation
    ANALYZE = "analyze"  # Analysis and insights
    VALIDATE = "validate"  # Validation and verification
    DECIDE = "decide"  # Decision making
    EXPLORE = "explore"  # Exploratory search
    COMPARE = "compare"  # Comparison tasks
    EXTRACT = "extract"  # Information extraction
    UNKNOWN = "unknown"


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"  # Single-step, direct answer
    MODERATE = "moderate"  # Multi-step, some reasoning
    COMPLEX = "complex"  # Multi-hop, significant reasoning
    EXPERT = "expert"  # Domain expertise required


class TaskRiskLevel(str, Enum):
    """Task risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskClassification:
    """Complete task classification result."""
    run_id: str
    
    # Primary classification
    task_type: TaskType
    task_subtype: Optional[str] = None
    
    # Complexity and risk
    complexity: TaskComplexity = TaskComplexity.MODERATE
    risk_level: TaskRiskLevel = TaskRiskLevel.LOW
    
    # Confidence
    confidence: float = 0.8
    classification_method: str = "rule_based"
    
    # Routing hints
    suggested_agents: List[str] = field(default_factory=list)
    suggested_tools: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    
    # Constraints derived from classification
    estimated_cost: float = 0.0
    estimated_latency_ms: int = 0
    requires_retrieval: bool = True
    requires_generation: bool = True
    requires_validation: bool = False
    
    # Features extracted
    features: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    classified_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.classified_at:
            self.classified_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_type": self.task_type.value,
            "task_subtype": self.task_subtype,
            "complexity": self.complexity.value,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
            "classification_method": self.classification_method,
            "suggested_agents": self.suggested_agents,
            "suggested_tools": self.suggested_tools,
            "required_capabilities": self.required_capabilities,
            "estimated_cost": self.estimated_cost,
            "estimated_latency_ms": self.estimated_latency_ms,
            "requires_retrieval": self.requires_retrieval,
            "requires_generation": self.requires_generation,
            "requires_validation": self.requires_validation,
            "features": self.features,
            "classified_at": self.classified_at,
            "schema_version": self.schema_version
        }


class TaskTypeClassifier:
    """
    Classifies incoming tasks for routing and policy selection.
    
    Outputs:
    - artifacts/task_type/{run_id}.json
    """
    
    # Keyword patterns for classification
    TASK_PATTERNS = {
        TaskType.RAG_QA: [
            "what is", "who is", "when did", "where is", "why does",
            "how does", "explain", "tell me", "describe", "define"
        ],
        TaskType.RAG_SUMMARY: [
            "summarize", "summary", "brief", "overview", "recap",
            "key points", "main ideas", "tldr", "tl;dr"
        ],
        TaskType.TRANSFORM: [
            "convert", "transform", "change", "format", "translate",
            "rewrite", "restructure", "adapt"
        ],
        TaskType.GENERATE: [
            "create", "generate", "write", "compose", "draft",
            "produce", "make", "build"
        ],
        TaskType.ANALYZE: [
            "analyze", "analysis", "evaluate", "assess", "review",
            "examine", "investigate", "study"
        ],
        TaskType.VALIDATE: [
            "validate", "verify", "check", "confirm", "ensure",
            "test", "audit", "inspect"
        ],
        TaskType.DECIDE: [
            "decide", "choose", "select", "recommend", "suggest",
            "should i", "which one", "best option"
        ],
        TaskType.EXPLORE: [
            "explore", "find", "search", "discover", "look for",
            "hunt", "seek", "locate"
        ],
        TaskType.COMPARE: [
            "compare", "versus", "vs", "difference", "similar",
            "contrast", "pros and cons"
        ],
        TaskType.EXTRACT: [
            "extract", "pull out", "identify", "list", "enumerate",
            "find all", "get the"
        ]
    }
    
    # Agent suggestions by task type
    AGENT_MAPPING = {
        TaskType.RAG_QA: ["data_agent", "execution_agent", "evaluation_agent"],
        TaskType.RAG_SUMMARY: ["data_agent", "execution_agent"],
        TaskType.TRANSFORM: ["execution_agent"],
        TaskType.GENERATE: ["execution_agent", "evaluation_agent"],
        TaskType.ANALYZE: ["data_agent", "execution_agent", "evaluation_agent"],
        TaskType.VALIDATE: ["evaluation_agent"],
        TaskType.DECIDE: ["data_agent", "execution_agent", "evaluation_agent"],
        TaskType.EXPLORE: ["data_agent", "execution_agent"],
        TaskType.COMPARE: ["data_agent", "execution_agent", "evaluation_agent"],
        TaskType.EXTRACT: ["data_agent", "execution_agent"]
    }
    
    # Tool suggestions by task type
    TOOL_MAPPING = {
        TaskType.RAG_QA: ["retriever", "reranker", "llm_generator"],
        TaskType.RAG_SUMMARY: ["retriever", "summarizer", "llm_generator"],
        TaskType.TRANSFORM: ["transformer", "formatter"],
        TaskType.GENERATE: ["llm_generator", "validator"],
        TaskType.ANALYZE: ["retriever", "analyzer", "llm_generator"],
        TaskType.VALIDATE: ["validator", "checker"],
        TaskType.DECIDE: ["retriever", "comparator", "llm_generator"],
        TaskType.EXPLORE: ["retriever", "crawler"],
        TaskType.COMPARE: ["retriever", "comparator", "llm_generator"],
        TaskType.EXTRACT: ["extractor", "parser"]
    }
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.task_type_dir = os.path.join(artifacts_dir, "task_type")
        os.makedirs(self.task_type_dir, exist_ok=True)
    
    def classify(
        self,
        run_id: str,
        task_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskClassification:
        """
        Classify a task.
        
        Args:
            run_id: Run identifier
            task_input: Task input (query, intent, etc.)
            context: Optional context
            
        Returns:
            TaskClassification
        """
        query = task_input.get("query", "").lower()
        intent = task_input.get("intent", "")
        
        # Extract features
        features = self._extract_features(query, task_input)
        
        # Classify task type
        task_type, confidence = self._classify_type(query, intent, features)
        
        # Determine complexity
        complexity = self._assess_complexity(query, features)
        
        # Determine risk level
        risk_level = self._assess_risk(task_input, features)
        
        # Get suggestions
        suggested_agents = self.AGENT_MAPPING.get(task_type, ["execution_agent"])
        suggested_tools = self.TOOL_MAPPING.get(task_type, ["llm_generator"])
        
        # Derive constraints
        requires_retrieval = task_type in [
            TaskType.RAG_QA, TaskType.RAG_SUMMARY, TaskType.ANALYZE,
            TaskType.DECIDE, TaskType.EXPLORE, TaskType.COMPARE
        ]
        requires_validation = task_type in [
            TaskType.VALIDATE, TaskType.GENERATE, TaskType.DECIDE
        ]
        
        # Estimate cost and latency
        estimated_cost, estimated_latency = self._estimate_resources(
            task_type, complexity, requires_retrieval
        )
        
        classification = TaskClassification(
            run_id=run_id,
            task_type=task_type,
            task_subtype=self._determine_subtype(task_type, features),
            complexity=complexity,
            risk_level=risk_level,
            confidence=confidence,
            classification_method="rule_based",
            suggested_agents=suggested_agents,
            suggested_tools=suggested_tools,
            required_capabilities=self._get_required_capabilities(task_type),
            estimated_cost=estimated_cost,
            estimated_latency_ms=estimated_latency,
            requires_retrieval=requires_retrieval,
            requires_generation=True,
            requires_validation=requires_validation,
            features=features
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
        
        return self._dict_to_classification(data)
    
    def _extract_features(
        self,
        query: str,
        task_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features from query."""
        words = query.split()
        
        return {
            "query_length": len(query),
            "word_count": len(words),
            "has_question_mark": "?" in query,
            "has_numbers": any(c.isdigit() for c in query),
            "has_code": any(kw in query for kw in ["code", "function", "class", "def", "import"]),
            "has_comparison": any(kw in query for kw in ["vs", "versus", "compare", "difference"]),
            "has_temporal": any(kw in query for kw in ["when", "date", "time", "year", "month"]),
            "has_location": any(kw in query for kw in ["where", "location", "place", "country"]),
            "explicit_intent": task_input.get("intent"),
            "has_constraints": bool(task_input.get("constraints"))
        }
    
    def _classify_type(
        self,
        query: str,
        intent: str,
        features: Dict[str, Any]
    ) -> tuple:
        """Classify task type with confidence."""
        scores = {}
        
        for task_type, patterns in self.TASK_PATTERNS.items():
            score = sum(1 for p in patterns if p in query)
            scores[task_type] = score
        
        # Use explicit intent if provided
        if intent:
            try:
                explicit_type = TaskType(intent)
                return explicit_type, 0.95
            except ValueError:
                pass
        
        # Get best match
        if max(scores.values()) > 0:
            best_type = max(scores, key=scores.get)
            confidence = min(0.9, 0.6 + scores[best_type] * 0.1)
            return best_type, confidence
        
        # Default to RAG_QA for questions
        if features.get("has_question_mark"):
            return TaskType.RAG_QA, 0.7
        
        return TaskType.UNKNOWN, 0.5
    
    def _assess_complexity(
        self,
        query: str,
        features: Dict[str, Any]
    ) -> TaskComplexity:
        """Assess task complexity."""
        word_count = features.get("word_count", 0)
        
        if word_count < 10:
            return TaskComplexity.SIMPLE
        elif word_count < 30:
            return TaskComplexity.MODERATE
        elif word_count < 60:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.EXPERT
    
    def _assess_risk(
        self,
        task_input: Dict[str, Any],
        features: Dict[str, Any]
    ) -> TaskRiskLevel:
        """Assess task risk level."""
        # Check for sensitive indicators
        if task_input.get("is_sensitive"):
            return TaskRiskLevel.HIGH
        
        if features.get("has_code"):
            return TaskRiskLevel.MEDIUM
        
        return TaskRiskLevel.LOW
    
    def _determine_subtype(
        self,
        task_type: TaskType,
        features: Dict[str, Any]
    ) -> Optional[str]:
        """Determine task subtype."""
        if task_type == TaskType.RAG_QA:
            if features.get("has_temporal"):
                return "temporal_qa"
            if features.get("has_location"):
                return "location_qa"
            if features.get("has_comparison"):
                return "comparative_qa"
        
        return None
    
    def _get_required_capabilities(self, task_type: TaskType) -> List[str]:
        """Get required capabilities for task type."""
        base = ["execute"]
        
        if task_type in [TaskType.RAG_QA, TaskType.RAG_SUMMARY, TaskType.EXPLORE]:
            base.extend(["retrieve", "generate"])
        elif task_type == TaskType.TRANSFORM:
            base.append("transform")
        elif task_type == TaskType.VALIDATE:
            base.append("validate")
        elif task_type == TaskType.ANALYZE:
            base.extend(["retrieve", "analyze", "generate"])
        
        return base
    
    def _estimate_resources(
        self,
        task_type: TaskType,
        complexity: TaskComplexity,
        requires_retrieval: bool
    ) -> tuple:
        """Estimate cost and latency."""
        base_cost = 0.02
        base_latency = 2000
        
        # Complexity multipliers
        complexity_mult = {
            TaskComplexity.SIMPLE: 1.0,
            TaskComplexity.MODERATE: 1.5,
            TaskComplexity.COMPLEX: 2.5,
            TaskComplexity.EXPERT: 4.0
        }
        
        mult = complexity_mult.get(complexity, 1.5)
        
        if requires_retrieval:
            base_cost += 0.01
            base_latency += 1000
        
        return round(base_cost * mult, 4), int(base_latency * mult)
    
    def _save_classification(self, classification: TaskClassification) -> None:
        """Save classification to artifact."""
        path = os.path.join(self.task_type_dir, f"{classification.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(classification.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _dict_to_classification(self, data: Dict[str, Any]) -> TaskClassification:
        """Convert dict to TaskClassification."""
        return TaskClassification(
            run_id=data["run_id"],
            task_type=TaskType(data["task_type"]),
            task_subtype=data.get("task_subtype"),
            complexity=TaskComplexity(data.get("complexity", "moderate")),
            risk_level=TaskRiskLevel(data.get("risk_level", "low")),
            confidence=data.get("confidence", 0.8),
            classification_method=data.get("classification_method", "rule_based"),
            suggested_agents=data.get("suggested_agents", []),
            suggested_tools=data.get("suggested_tools", []),
            required_capabilities=data.get("required_capabilities", []),
            estimated_cost=data.get("estimated_cost", 0.0),
            estimated_latency_ms=data.get("estimated_latency_ms", 0),
            requires_retrieval=data.get("requires_retrieval", True),
            requires_generation=data.get("requires_generation", True),
            requires_validation=data.get("requires_validation", False),
            features=data.get("features", {}),
            classified_at=data.get("classified_at", ""),
            schema_version=data.get("schema_version", "1.0")
        )



