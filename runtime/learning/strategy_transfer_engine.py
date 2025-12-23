"""
Cross-Layer Strategy Transfer Engine.

Enables the system to respond to failures in Layer A by adjusting strategies in Layer B.
This is a key differentiator from Devin/AlphaDev which only optimize "where failure occurred".

Example transfers:
- Tool failure → Change Prompt / Tool selection strategy
- Retrieval conflict → Change Tool choice / Evidence weighting
- Prompt injection → Tighten Planner constraints
- Planner error → Expand Retrieval breadth
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class SourceLayer(str, Enum):
    """Source of failure."""
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    PROMPT = "prompt"
    PLANNER = "planner"
    EVIDENCE = "evidence"
    GENERATION = "generation"


class TargetLayer(str, Enum):
    """Target for strategy change."""
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    PROMPT = "prompt"
    PLANNER = "planner"
    EVIDENCE = "evidence"
    GENERATION = "generation"


@dataclass
class TransferRule:
    """A single cross-layer transfer rule."""
    rule_id: str
    source_layer: SourceLayer
    source_failure_types: List[str]
    target_layer: TargetLayer
    strategy_change: str
    rationale: str
    confidence_weight: float = 1.0
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["source_layer"] = self.source_layer.value
        result["target_layer"] = self.target_layer.value
        return result


@dataclass
class TransferProposal:
    """A proposed cross-layer strategy change."""
    proposal_id: str
    source_layer: str
    source_failure: str
    target_layer: str
    strategy_change: str
    rationale: str
    confidence: float
    rule_id: str
    shadow_required: bool = True
    replay_required: bool = True
    gate_thresholds: Dict[str, float] = field(default_factory=dict)
    status: str = "proposed"  # proposed, shadowing, passed, rejected, rolled_out
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StrategyTransferEngine:
    """
    Cross-Layer Strategy Transfer Engine.
    
    Takes attribution artifacts and proposes strategy changes in different layers
    than where the failure occurred.
    """
    
    # Default transfer rules (configurable)
    DEFAULT_RULES = [
        # Tool failure → Change Prompt / Tool selection
        TransferRule(
            rule_id="tool_to_prompt_001",
            source_layer=SourceLayer.TOOL,
            source_failure_types=["TOOL_TIMEOUT", "TOOL_PARTIAL_FAILURE"],
            target_layer=TargetLayer.PROMPT,
            strategy_change="reduce_tool_reliance",
            rationale="When tools fail, reduce prompt's dependency on tool outputs",
            confidence_weight=0.8
        ),
        TransferRule(
            rule_id="tool_to_tool_002",
            source_layer=SourceLayer.TOOL,
            source_failure_types=["TOOL_TIMEOUT"],
            target_layer=TargetLayer.TOOL,
            strategy_change="switch_to_fallback_tool",
            rationale="Use alternative tool with better reliability",
            confidence_weight=0.9
        ),
        
        # Retrieval conflict → Tool choice / Evidence weighting
        TransferRule(
            rule_id="retrieval_to_tool_001",
            source_layer=SourceLayer.RETRIEVAL,
            source_failure_types=["RETRIEVAL_CONFLICT"],
            target_layer=TargetLayer.TOOL,
            strategy_change="add_conflict_resolution_tool",
            rationale="Add tool to resolve conflicting retrieval results",
            confidence_weight=0.7
        ),
        TransferRule(
            rule_id="retrieval_to_evidence_001",
            source_layer=SourceLayer.RETRIEVAL,
            source_failure_types=["RETRIEVAL_CONFLICT"],
            target_layer=TargetLayer.EVIDENCE,
            strategy_change="increase_evidence_threshold",
            rationale="Raise evidence quality threshold to filter conflicts",
            confidence_weight=0.8
        ),
        
        # Prompt injection → Planner constraints
        TransferRule(
            rule_id="prompt_to_planner_001",
            source_layer=SourceLayer.PROMPT,
            source_failure_types=["PROMPT_INJECTION"],
            target_layer=TargetLayer.PLANNER,
            strategy_change="add_safety_constraints",
            rationale="Tighten planner DAG to prevent injection paths",
            confidence_weight=0.85
        ),
        TransferRule(
            rule_id="prompt_to_prompt_001",
            source_layer=SourceLayer.PROMPT,
            source_failure_types=["PROMPT_INJECTION"],
            target_layer=TargetLayer.PROMPT,
            strategy_change="harden_prompt_template",
            rationale="Use hardened prompt template with injection guards",
            confidence_weight=0.9
        ),
        
        # Planner error → Retrieval breadth
        TransferRule(
            rule_id="planner_to_retrieval_001",
            source_layer=SourceLayer.PLANNER,
            source_failure_types=["PLANNER_WRONG_DAG"],
            target_layer=TargetLayer.RETRIEVAL,
            strategy_change="increase_retrieval_breadth",
            rationale="Expand retrieval to provide more context for planning",
            confidence_weight=0.75
        ),
        TransferRule(
            rule_id="planner_to_prompt_001",
            source_layer=SourceLayer.PLANNER,
            source_failure_types=["PLANNER_WRONG_DAG"],
            target_layer=TargetLayer.PROMPT,
            strategy_change="add_planning_hints",
            rationale="Add explicit planning hints in prompt",
            confidence_weight=0.7
        ),
        
        # Evidence insufficient → Retrieval strategy
        TransferRule(
            rule_id="evidence_to_retrieval_001",
            source_layer=SourceLayer.EVIDENCE,
            source_failure_types=["EVIDENCE_INSUFFICIENT"],
            target_layer=TargetLayer.RETRIEVAL,
            strategy_change="increase_top_k",
            rationale="Retrieve more documents to improve evidence coverage",
            confidence_weight=0.85
        ),
        
        # Generation hallucination → Evidence / Retrieval
        TransferRule(
            rule_id="generation_to_evidence_001",
            source_layer=SourceLayer.GENERATION,
            source_failure_types=["GENERATION_HALLUCINATION"],
            target_layer=TargetLayer.EVIDENCE,
            strategy_change="require_citation",
            rationale="Require citation for each claim to reduce hallucination",
            confidence_weight=0.8
        ),
        TransferRule(
            rule_id="generation_to_retrieval_001",
            source_layer=SourceLayer.GENERATION,
            source_failure_types=["GENERATION_HALLUCINATION"],
            target_layer=TargetLayer.RETRIEVAL,
            strategy_change="enable_fact_checking",
            rationale="Add fact-checking retrieval pass",
            confidence_weight=0.75
        ),
    ]
    
    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        custom_rules: Optional[List[TransferRule]] = None
    ):
        self.artifacts_dir = artifacts_dir
        self.rules = custom_rules or self.DEFAULT_RULES
        self.proposals: List[TransferProposal] = []
        
        # Load existing proposals
        self._load_proposals()
    
    def analyze_attribution(
        self,
        attribution: Dict[str, Any]
    ) -> List[TransferProposal]:
        """
        Analyze attribution artifact and generate cross-layer transfer proposals.
        
        Args:
            attribution: Attribution artifact with primary_cause, layer_blame_weights, etc.
            
        Returns:
            List of TransferProposal
        """
        if not attribution.get("failure", False):
            return []
        
        proposals = []
        primary_cause = attribution.get("primary_cause", "")
        primary_layer = attribution.get("primary_layer", "")
        confidence = attribution.get("confidence", 0.0)
        layer_weights = attribution.get("layer_blame_weights", {})
        run_id = attribution.get("run_id", "unknown")
        
        # Find matching transfer rules
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check if rule matches the failure
            if rule.source_layer.value != primary_layer:
                continue
            
            if primary_cause not in rule.source_failure_types:
                continue
            
            # Generate proposal
            proposal_id = self._generate_proposal_id(run_id, rule.rule_id)
            
            # Cross-layer check: is target different from source?
            is_cross_layer = rule.target_layer.value != primary_layer
            
            proposal = TransferProposal(
                proposal_id=proposal_id,
                source_layer=primary_layer,
                source_failure=primary_cause,
                target_layer=rule.target_layer.value,
                strategy_change=rule.strategy_change,
                rationale=rule.rationale,
                confidence=confidence * rule.confidence_weight,
                rule_id=rule.rule_id,
                shadow_required=True,
                replay_required=True,
                gate_thresholds={
                    "min_success_uplift": 0.0,
                    "max_cost_increase": 0.10,
                    "max_latency_increase": 0.15
                },
                status="proposed"
            )
            
            proposals.append(proposal)
            self.proposals.append(proposal)
        
        # Save proposals
        self._save_proposals(run_id, proposals)
        
        return proposals
    
    def get_cross_layer_proposals(self) -> List[TransferProposal]:
        """Get all proposals where source != target layer."""
        return [
            p for p in self.proposals
            if p.source_layer != p.target_layer
        ]
    
    def update_proposal_status(
        self,
        proposal_id: str,
        new_status: str,
        evaluation_result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update proposal status after shadow/replay/gate evaluation.
        
        Args:
            proposal_id: Proposal ID
            new_status: New status (shadowing, passed, rejected, rolled_out)
            evaluation_result: Optional evaluation details
            
        Returns:
            True if updated, False if not found
        """
        for proposal in self.proposals:
            if proposal.proposal_id == proposal_id:
                proposal.status = new_status
                self._save_all_proposals()
                return True
        return False
    
    def verify_shadow_gate(
        self,
        proposal_id: str,
        shadow_result: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify if proposal passes shadow evaluation gate.
        
        Args:
            proposal_id: Proposal ID
            shadow_result: Shadow execution result
            
        Returns:
            (passed, details)
        """
        proposal = None
        for p in self.proposals:
            if p.proposal_id == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return False, {"error": "proposal_not_found"}
        
        thresholds = proposal.gate_thresholds
        
        # Check success uplift
        success_uplift = shadow_result.get("success_delta", 0.0)
        min_uplift = thresholds.get("min_success_uplift", 0.0)
        if success_uplift < min_uplift:
            return False, {
                "reason": "success_uplift_too_low",
                "value": success_uplift,
                "threshold": min_uplift
            }
        
        # Check cost increase
        cost_increase = shadow_result.get("cost_delta_pct", 0.0)
        max_cost = thresholds.get("max_cost_increase", 0.10)
        if cost_increase > max_cost:
            return False, {
                "reason": "cost_increase_too_high",
                "value": cost_increase,
                "threshold": max_cost
            }
        
        # Check latency increase
        latency_increase = shadow_result.get("latency_delta_pct", 0.0)
        max_latency = thresholds.get("max_latency_increase", 0.15)
        if latency_increase > max_latency:
            return False, {
                "reason": "latency_increase_too_high",
                "value": latency_increase,
                "threshold": max_latency
            }
        
        return True, {"reason": "all_gates_passed"}
    
    def verify_regression_gate(
        self,
        proposal_id: str,
        regression_result: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify if proposal passes regression/golden replay gate.
        
        Args:
            proposal_id: Proposal ID
            regression_result: Regression test result
            
        Returns:
            (passed, details)
        """
        if not regression_result.get("safe_to_rollout", False):
            return False, {
                "reason": "regression_detected",
                "blocking_reasons": regression_result.get("blocking_reasons", [])
            }
        
        return True, {"reason": "no_regression"}
    
    def _generate_proposal_id(self, run_id: str, rule_id: str) -> str:
        """Generate unique proposal ID."""
        content = f"{run_id}:{rule_id}:{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _save_proposals(self, run_id: str, proposals: List[TransferProposal]) -> None:
        """Save proposals for a specific run."""
        if not proposals:
            return
        
        strategy_dir = os.path.join(self.artifacts_dir, "strategy")
        os.makedirs(strategy_dir, exist_ok=True)
        
        # Save cross-layer candidates
        cross_layer_path = os.path.join(strategy_dir, "cross_layer_candidates.json")
        
        # Load existing
        existing = []
        if os.path.exists(cross_layer_path):
            try:
                with open(cross_layer_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    existing = data.get("candidates", [])
            except (json.JSONDecodeError, IOError):
                pass
        
        # Add new (only cross-layer)
        for p in proposals:
            if p.source_layer != p.target_layer:
                existing.append({
                    "run_id": run_id,
                    "proposal": p.to_dict(),
                    "timestamp": datetime.now().isoformat()
                })
        
        # Save
        with open(cross_layer_path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "candidates": existing[-1000:],  # Keep last 1000
                "generated_at": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    
    def _save_all_proposals(self) -> None:
        """Save all proposals to artifact."""
        strategy_dir = os.path.join(self.artifacts_dir, "strategy")
        os.makedirs(strategy_dir, exist_ok=True)
        
        path = os.path.join(strategy_dir, "all_proposals.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "proposals": [p.to_dict() for p in self.proposals[-1000:]],
                "generated_at": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
    
    def _load_proposals(self) -> None:
        """Load existing proposals."""
        path = os.path.join(self.artifacts_dir, "strategy", "all_proposals.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for p_data in data.get("proposals", []):
                self.proposals.append(TransferProposal(
                    proposal_id=p_data.get("proposal_id", ""),
                    source_layer=p_data.get("source_layer", ""),
                    source_failure=p_data.get("source_failure", ""),
                    target_layer=p_data.get("target_layer", ""),
                    strategy_change=p_data.get("strategy_change", ""),
                    rationale=p_data.get("rationale", ""),
                    confidence=p_data.get("confidence", 0.0),
                    rule_id=p_data.get("rule_id", ""),
                    shadow_required=p_data.get("shadow_required", True),
                    replay_required=p_data.get("replay_required", True),
                    gate_thresholds=p_data.get("gate_thresholds", {}),
                    status=p_data.get("status", "proposed")
                ))
        except (json.JSONDecodeError, IOError):
            pass


def process_attribution_and_propose_transfers(
    attribution_path: str,
    artifacts_dir: str = "artifacts"
) -> List[Dict[str, Any]]:
    """
    Convenience function to process attribution and generate cross-layer proposals.
    
    Args:
        attribution_path: Path to attribution JSON file
        artifacts_dir: Artifacts directory
        
    Returns:
        List of proposal dicts
    """
    with open(attribution_path, "r", encoding="utf-8") as f:
        attribution = json.load(f)
    
    engine = StrategyTransferEngine(artifacts_dir=artifacts_dir)
    proposals = engine.analyze_attribution(attribution)
    
    return [p.to_dict() for p in proposals]



