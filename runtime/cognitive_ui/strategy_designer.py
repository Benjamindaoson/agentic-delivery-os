"""
Strategy Designer: User-Designed Strategy Composition
P1-1 Implementation: Non-engineers can design strategies through UI

This module provides:
1. Strategy composition interface for non-engineers
2. Weight/threshold/agent toggle adjustments
3. Mapping UI actions to executable policies
4. Governance review integration
5. Rollback capability
"""

import os
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    """Status of a user-designed strategy"""
    DRAFT = "draft"                  # Being designed
    PENDING_REVIEW = "pending_review"  # Awaiting governance review
    APPROVED = "approved"            # Approved, ready for use
    REJECTED = "rejected"            # Rejected by governance
    ACTIVE = "active"                # Currently in use
    DEPRECATED = "deprecated"        # No longer active
    ROLLED_BACK = "rolled_back"      # Rolled back from active


class ComponentType(str, Enum):
    """Types of strategy components"""
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    TOOL = "tool"
    AGENT = "agent"
    PLANNER = "planner"
    EVALUATOR = "evaluator"


@dataclass
class StrategyComponent:
    """A single component in a user-designed strategy"""
    component_id: str
    component_type: ComponentType
    name: str
    enabled: bool = True
    weight: float = 1.0
    config: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "weight": self.weight,
            "config": self.config,
            "description": self.description
        }


@dataclass
class StrategyThreshold:
    """Configurable threshold in a strategy"""
    threshold_id: str
    name: str
    description: str
    min_value: float
    max_value: float
    current_value: float
    unit: str = ""
    category: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UserDesignedStrategy:
    """Complete user-designed strategy"""
    strategy_id: str
    name: str
    description: str
    created_by: str
    
    # Components
    components: List[StrategyComponent] = field(default_factory=list)
    
    # Thresholds
    thresholds: List[StrategyThreshold] = field(default_factory=list)
    
    # Agent toggles
    agent_toggles: Dict[str, bool] = field(default_factory=dict)
    
    # Execution preferences
    execution_mode: str = "normal"  # normal, conservative, aggressive
    max_cost: float = 1.0
    max_latency_ms: int = 5000
    
    # Status tracking
    status: StrategyStatus = StrategyStatus.DRAFT
    version: int = 1
    parent_version: Optional[str] = None
    
    # Audit
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    governance_review: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "components": [c.to_dict() for c in self.components],
            "thresholds": [t.to_dict() for t in self.thresholds],
            "agent_toggles": self.agent_toggles,
            "execution_mode": self.execution_mode,
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms,
            "status": self.status.value,
            "version": self.version,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "governance_review": self.governance_review
        }
    
    def compute_hash(self) -> str:
        """Compute deterministic hash for the strategy"""
        content = json.dumps({
            "components": [c.to_dict() for c in self.components],
            "thresholds": [t.to_dict() for t in self.thresholds],
            "agent_toggles": self.agent_toggles,
            "execution_mode": self.execution_mode,
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class StrategyDesignerAPI:
    """
    API for strategy design operations.
    Provides CRUD operations for user-designed strategies.
    """
    
    # Available component templates
    COMPONENT_TEMPLATES = {
        "retrieval": [
            StrategyComponent(
                component_id="semantic_retrieval",
                component_type=ComponentType.RETRIEVAL,
                name="Semantic Search",
                description="Vector-based semantic search",
                config={"top_k": 10, "similarity_threshold": 0.7}
            ),
            StrategyComponent(
                component_id="keyword_retrieval",
                component_type=ComponentType.RETRIEVAL,
                name="Keyword Search",
                description="BM25-based keyword search",
                config={"top_k": 20}
            ),
            StrategyComponent(
                component_id="hybrid_retrieval",
                component_type=ComponentType.RETRIEVAL,
                name="Hybrid Search",
                description="Combined semantic + keyword",
                config={"semantic_weight": 0.7, "keyword_weight": 0.3}
            )
        ],
        "generation": [
            StrategyComponent(
                component_id="standard_gen",
                component_type=ComponentType.GENERATION,
                name="Standard Generation",
                description="Single-pass generation",
                config={"temperature": 0.7}
            ),
            StrategyComponent(
                component_id="iterative_gen",
                component_type=ComponentType.GENERATION,
                name="Iterative Refinement",
                description="Multi-pass with self-critique",
                config={"max_iterations": 3}
            )
        ],
        "agent": [
            StrategyComponent(
                component_id="product_agent",
                component_type=ComponentType.AGENT,
                name="Product Agent",
                description="Validates task feasibility",
                config={}
            ),
            StrategyComponent(
                component_id="data_agent",
                component_type=ComponentType.AGENT,
                name="Data Agent",
                description="Handles data gathering",
                config={}
            ),
            StrategyComponent(
                component_id="eval_agent",
                component_type=ComponentType.AGENT,
                name="Evaluation Agent",
                description="Quality evaluation",
                config={}
            )
        ]
    }
    
    # Default thresholds
    DEFAULT_THRESHOLDS = [
        StrategyThreshold(
            threshold_id="quality_min",
            name="Minimum Quality",
            description="Minimum acceptable quality score",
            min_value=0.0,
            max_value=1.0,
            current_value=0.7,
            category="quality"
        ),
        StrategyThreshold(
            threshold_id="cost_max",
            name="Maximum Cost",
            description="Maximum cost per task",
            min_value=0.0,
            max_value=10.0,
            current_value=1.0,
            unit="USD",
            category="cost"
        ),
        StrategyThreshold(
            threshold_id="latency_max",
            name="Maximum Latency",
            description="Maximum response time",
            min_value=100,
            max_value=30000,
            current_value=5000,
            unit="ms",
            category="latency"
        ),
        StrategyThreshold(
            threshold_id="retrieval_k",
            name="Retrieval Top-K",
            description="Number of documents to retrieve",
            min_value=1,
            max_value=100,
            current_value=10,
            category="retrieval"
        )
    ]
    
    def __init__(self, storage_path: str = "artifacts/strategies"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self.strategies: Dict[str, UserDesignedStrategy] = {}
        self._load_strategies()
    
    def create_strategy(
        self,
        name: str,
        description: str,
        created_by: str,
        template: str = "default"
    ) -> UserDesignedStrategy:
        """Create a new strategy from template"""
        strategy_id = f"strategy_{uuid.uuid4().hex[:12]}"
        
        # Initialize with template components
        components = []
        if template == "default":
            components = [
                self.COMPONENT_TEMPLATES["retrieval"][0],  # Semantic search
                self.COMPONENT_TEMPLATES["generation"][0],  # Standard gen
            ]
        elif template == "advanced":
            components = [
                self.COMPONENT_TEMPLATES["retrieval"][2],  # Hybrid
                self.COMPONENT_TEMPLATES["generation"][1],  # Iterative
            ]
        
        # Initialize with default thresholds
        thresholds = [StrategyThreshold(**asdict(t)) for t in self.DEFAULT_THRESHOLDS]
        
        # Default agent toggles
        agent_toggles = {
            "Product": True,
            "Data": True,
            "Execution": True,
            "Evaluation": True,
            "Cost": True
        }
        
        strategy = UserDesignedStrategy(
            strategy_id=strategy_id,
            name=name,
            description=description,
            created_by=created_by,
            components=components,
            thresholds=thresholds,
            agent_toggles=agent_toggles
        )
        
        self.strategies[strategy_id] = strategy
        self._save_strategy(strategy)
        
        return strategy
    
    def update_component(
        self,
        strategy_id: str,
        component_id: str,
        updates: Dict[str, Any]
    ) -> Optional[StrategyComponent]:
        """Update a component in a strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        for component in strategy.components:
            if component.component_id == component_id:
                if "enabled" in updates:
                    component.enabled = updates["enabled"]
                if "weight" in updates:
                    component.weight = updates["weight"]
                if "config" in updates:
                    component.config.update(updates["config"])
                
                strategy.updated_at = datetime.now().isoformat()
                self._save_strategy(strategy)
                return component
        
        return None
    
    def update_threshold(
        self,
        strategy_id: str,
        threshold_id: str,
        new_value: float
    ) -> Optional[StrategyThreshold]:
        """Update a threshold value"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        for threshold in strategy.thresholds:
            if threshold.threshold_id == threshold_id:
                # Validate range
                if threshold.min_value <= new_value <= threshold.max_value:
                    threshold.current_value = new_value
                    strategy.updated_at = datetime.now().isoformat()
                    self._save_strategy(strategy)
                    return threshold
        
        return None
    
    def toggle_agent(
        self,
        strategy_id: str,
        agent_name: str,
        enabled: bool
    ) -> bool:
        """Toggle an agent on/off"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        strategy.agent_toggles[agent_name] = enabled
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        return True
    
    def add_component(
        self,
        strategy_id: str,
        component_type: str,
        template_id: str
    ) -> Optional[StrategyComponent]:
        """Add a component from template"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        # Find template
        templates = self.COMPONENT_TEMPLATES.get(component_type, [])
        template = next((t for t in templates if t.component_id == template_id), None)
        if not template:
            return None
        
        # Create new component instance
        new_component = StrategyComponent(
            component_id=f"{template_id}_{len(strategy.components)}",
            component_type=template.component_type,
            name=template.name,
            description=template.description,
            config=dict(template.config)
        )
        
        strategy.components.append(new_component)
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return new_component
    
    def remove_component(
        self,
        strategy_id: str,
        component_id: str
    ) -> bool:
        """Remove a component from strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        original_len = len(strategy.components)
        strategy.components = [c for c in strategy.components if c.component_id != component_id]
        
        if len(strategy.components) < original_len:
            strategy.updated_at = datetime.now().isoformat()
            self._save_strategy(strategy)
            return True
        
        return False
    
    def submit_for_review(self, strategy_id: str) -> bool:
        """Submit strategy for governance review"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.DRAFT:
            return False
        
        strategy.status = StrategyStatus.PENDING_REVIEW
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return True
    
    def approve_strategy(
        self,
        strategy_id: str,
        reviewer: str,
        comments: str = ""
    ) -> bool:
        """Approve a strategy after governance review"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.PENDING_REVIEW:
            return False
        
        strategy.status = StrategyStatus.APPROVED
        strategy.governance_review = {
            "reviewer": reviewer,
            "decision": "approved",
            "comments": comments,
            "reviewed_at": datetime.now().isoformat()
        }
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return True
    
    def reject_strategy(
        self,
        strategy_id: str,
        reviewer: str,
        reason: str
    ) -> bool:
        """Reject a strategy during governance review"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.PENDING_REVIEW:
            return False
        
        strategy.status = StrategyStatus.REJECTED
        strategy.governance_review = {
            "reviewer": reviewer,
            "decision": "rejected",
            "reason": reason,
            "reviewed_at": datetime.now().isoformat()
        }
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return True
    
    def activate_strategy(self, strategy_id: str) -> bool:
        """Activate an approved strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.APPROVED:
            return False
        
        strategy.status = StrategyStatus.ACTIVE
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return True
    
    def rollback_strategy(
        self,
        strategy_id: str,
        reason: str
    ) -> bool:
        """Rollback an active strategy"""
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return False
        
        if strategy.status != StrategyStatus.ACTIVE:
            return False
        
        strategy.status = StrategyStatus.ROLLED_BACK
        strategy.governance_review = strategy.governance_review or {}
        strategy.governance_review["rollback"] = {
            "reason": reason,
            "rolled_back_at": datetime.now().isoformat()
        }
        strategy.updated_at = datetime.now().isoformat()
        self._save_strategy(strategy)
        
        return True
    
    def get_strategy(self, strategy_id: str) -> Optional[UserDesignedStrategy]:
        """Get a strategy by ID"""
        return self.strategies.get(strategy_id)
    
    def list_strategies(
        self,
        status: Optional[StrategyStatus] = None,
        created_by: Optional[str] = None
    ) -> List[UserDesignedStrategy]:
        """List strategies with optional filters"""
        strategies = list(self.strategies.values())
        
        if status:
            strategies = [s for s in strategies if s.status == status]
        
        if created_by:
            strategies = [s for s in strategies if s.created_by == created_by]
        
        return strategies
    
    def convert_to_executable_policy(
        self,
        strategy_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convert user-designed strategy to executable policy format.
        This is the key mapping from UI design to runtime execution.
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return None
        
        # Build policy structure
        policy = {
            "policy_id": f"policy_{strategy.strategy_id}_{strategy.version}",
            "strategy_hash": strategy.compute_hash(),
            "created_from": strategy.strategy_id,
            "created_at": datetime.now().isoformat(),
            
            # Retrieval configuration
            "retrieval": {
                "enabled": any(c.enabled for c in strategy.components 
                             if c.component_type == ComponentType.RETRIEVAL),
                "components": [
                    {
                        "id": c.component_id,
                        "weight": c.weight,
                        "config": c.config
                    }
                    for c in strategy.components
                    if c.component_type == ComponentType.RETRIEVAL and c.enabled
                ]
            },
            
            # Generation configuration
            "generation": {
                "enabled": any(c.enabled for c in strategy.components 
                             if c.component_type == ComponentType.GENERATION),
                "components": [
                    {
                        "id": c.component_id,
                        "weight": c.weight,
                        "config": c.config
                    }
                    for c in strategy.components
                    if c.component_type == ComponentType.GENERATION and c.enabled
                ]
            },
            
            # Agent configuration
            "agents": {
                name: {"enabled": enabled, "weight": 1.0}
                for name, enabled in strategy.agent_toggles.items()
            },
            
            # Thresholds as constraints
            "constraints": {
                t.threshold_id: t.current_value
                for t in strategy.thresholds
            },
            
            # Execution preferences
            "execution": {
                "mode": strategy.execution_mode,
                "max_cost": strategy.max_cost,
                "max_latency_ms": strategy.max_latency_ms
            },
            
            # Governance metadata
            "governance": {
                "status": strategy.status.value,
                "review": strategy.governance_review
            }
        }
        
        return policy
    
    def get_available_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get available component templates for UI"""
        return {
            category: [c.to_dict() for c in components]
            for category, components in self.COMPONENT_TEMPLATES.items()
        }
    
    def _save_strategy(self, strategy: UserDesignedStrategy):
        """Persist strategy to disk"""
        path = os.path.join(self.storage_path, f"{strategy.strategy_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(strategy.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_strategies(self):
        """Load all strategies from disk"""
        if not os.path.exists(self.storage_path):
            return
        
        for filename in os.listdir(self.storage_path):
            if not filename.endswith(".json"):
                continue
            
            path = os.path.join(self.storage_path, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Reconstruct strategy
                strategy = UserDesignedStrategy(
                    strategy_id=data["strategy_id"],
                    name=data["name"],
                    description=data["description"],
                    created_by=data["created_by"],
                    components=[
                        StrategyComponent(
                            component_id=c["component_id"],
                            component_type=ComponentType(c["component_type"]),
                            name=c["name"],
                            enabled=c.get("enabled", True),
                            weight=c.get("weight", 1.0),
                            config=c.get("config", {}),
                            description=c.get("description", "")
                        )
                        for c in data.get("components", [])
                    ],
                    thresholds=[
                        StrategyThreshold(**t)
                        for t in data.get("thresholds", [])
                    ],
                    agent_toggles=data.get("agent_toggles", {}),
                    execution_mode=data.get("execution_mode", "normal"),
                    max_cost=data.get("max_cost", 1.0),
                    max_latency_ms=data.get("max_latency_ms", 5000),
                    status=StrategyStatus(data.get("status", "draft")),
                    version=data.get("version", 1),
                    parent_version=data.get("parent_version"),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    governance_review=data.get("governance_review")
                )
                
                self.strategies[strategy.strategy_id] = strategy
            except Exception as e:
                print(f"Warning: Could not load strategy {filename}: {e}")


# Global strategy designer
_designer: Optional[StrategyDesignerAPI] = None

def get_strategy_designer() -> StrategyDesignerAPI:
    """Get global strategy designer instance"""
    global _designer
    if _designer is None:
        _designer = StrategyDesignerAPI()
    return _designer


