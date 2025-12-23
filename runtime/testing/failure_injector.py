"""
Failure Injector: Deterministic, tagged failure injection for L5 attribution verification.
Test-only module. Must not affect production execution.
"""
import os
import json
import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict, field


class FailureType(str, Enum):
    """Supported failure types for injection."""
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_PARTIAL_FAILURE = "TOOL_PARTIAL_FAILURE"
    RETRIEVAL_CONFLICT = "RETRIEVAL_CONFLICT"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    PLANNER_WRONG_DAG = "PLANNER_WRONG_DAG"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    GENERATION_HALLUCINATION = "GENERATION_HALLUCINATION"


@dataclass
class InjectedFailure:
    """Represents a single injected failure."""
    failure_type: FailureType
    layer: str  # tool, retrieval, prompt, planner, evidence, generation
    severity: float  # 0.0-1.0
    deterministic_seed: int
    inject_at_step: int  # which step to inject at
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["failure_type"] = self.failure_type.value
        return result
    
    def to_tag(self) -> str:
        """Generate deterministic tag for this injection."""
        content = f"{self.failure_type.value}:{self.layer}:{self.severity}:{self.deterministic_seed}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class InjectionPlan:
    """Plan for injecting failures into a run."""
    run_id: str
    failures: List[InjectedFailure]
    created_at: str = ""
    plan_hash: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.plan_hash:
            content = json.dumps([f.to_dict() for f in self.failures], sort_keys=True)
            self.plan_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "failures": [f.to_dict() for f in self.failures],
            "created_at": self.created_at,
            "plan_hash": self.plan_hash
        }


class FailureInjector:
    """
    Deterministic failure injector for testing attribution accuracy.
    
    Guarantees:
    - Failures are tagged and traceable
    - Injection is deterministic (same seed = same behavior)
    - Does not pollute active execution (test-only)
    """
    
    # Layer mapping for failure types
    FAILURE_LAYER_MAP = {
        FailureType.TOOL_TIMEOUT: "tool",
        FailureType.TOOL_PARTIAL_FAILURE: "tool",
        FailureType.RETRIEVAL_CONFLICT: "retrieval",
        FailureType.PROMPT_INJECTION: "prompt",
        FailureType.PLANNER_WRONG_DAG: "planner",
        FailureType.ENVIRONMENT_ERROR: "environment",
        FailureType.EVIDENCE_INSUFFICIENT: "evidence",
        FailureType.GENERATION_HALLUCINATION: "generation",
    }
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.injection_plans: Dict[str, InjectionPlan] = {}
        self._active_injections: Dict[str, Set[str]] = {}  # run_id -> set of failure tags
    
    def create_injection_plan(
        self,
        run_id: str,
        failure_types: List[FailureType],
        seed: int = 42,
        severity: float = 1.0
    ) -> InjectionPlan:
        """
        Create a deterministic injection plan.
        
        Args:
            run_id: Target run ID
            failure_types: List of failure types to inject
            seed: Deterministic seed
            severity: Failure severity (0.0-1.0)
            
        Returns:
            InjectionPlan
        """
        failures = []
        for i, ft in enumerate(failure_types):
            layer = self.FAILURE_LAYER_MAP.get(ft, "unknown")
            failures.append(InjectedFailure(
                failure_type=ft,
                layer=layer,
                severity=severity,
                deterministic_seed=seed + i,
                inject_at_step=i,
                metadata={"index": i}
            ))
        
        plan = InjectionPlan(run_id=run_id, failures=failures)
        self.injection_plans[run_id] = plan
        
        # Save plan to artifact
        self._save_plan(plan)
        
        return plan
    
    def inject(self, run_id: str, current_step: int, layer: str) -> Optional[InjectedFailure]:
        """
        Check if a failure should be injected at this point.
        
        Args:
            run_id: Run ID
            current_step: Current execution step
            layer: Current layer being executed
            
        Returns:
            InjectedFailure if injection should occur, None otherwise
        """
        plan = self.injection_plans.get(run_id)
        if not plan:
            return None
        
        for failure in plan.failures:
            if failure.inject_at_step == current_step and failure.layer == layer:
                # Track injection
                if run_id not in self._active_injections:
                    self._active_injections[run_id] = set()
                self._active_injections[run_id].add(failure.to_tag())
                return failure
        
        return None
    
    def get_injected_failures(self, run_id: str) -> List[InjectedFailure]:
        """Get all failures injected for a run."""
        plan = self.injection_plans.get(run_id)
        if not plan:
            return []
        return plan.failures
    
    def get_expected_root_cause(self, run_id: str) -> Optional[str]:
        """
        Get the expected primary root cause for a run.
        
        The primary cause is the first failure in injection order
        (highest severity if equal).
        """
        plan = self.injection_plans.get(run_id)
        if not plan or not plan.failures:
            return None
        
        # Sort by severity (desc), then by step (asc)
        sorted_failures = sorted(
            plan.failures,
            key=lambda f: (-f.severity, f.inject_at_step)
        )
        
        return sorted_failures[0].failure_type.value
    
    def get_expected_layer_weights(self, run_id: str) -> Dict[str, float]:
        """
        Get expected blame weights by layer.
        
        Weights sum to 1.0, distributed by severity.
        """
        plan = self.injection_plans.get(run_id)
        if not plan or not plan.failures:
            return {}
        
        total_severity = sum(f.severity for f in plan.failures)
        if total_severity == 0:
            return {}
        
        weights: Dict[str, float] = {}
        for failure in plan.failures:
            layer = failure.layer
            weight = failure.severity / total_severity
            weights[layer] = weights.get(layer, 0.0) + weight
        
        return weights
    
    def validate_attribution(
        self,
        run_id: str,
        attribution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate attribution against injection plan.
        
        Returns validation result with pass/fail and reasons.
        """
        plan = self.injection_plans.get(run_id)
        if not plan:
            return {
                "valid": False,
                "reason": "no_injection_plan",
                "details": {}
            }
        
        errors = []
        warnings = []
        
        # Check 1: Primary cause matches expected
        expected_cause = self.get_expected_root_cause(run_id)
        detected_cause = attribution.get("primary_cause")
        
        if not detected_cause:
            errors.append("attribution_missing_primary_cause")
        elif detected_cause != expected_cause:
            # Check if it's a related cause (same layer)
            expected_layer = None
            for f in plan.failures:
                if f.failure_type.value == expected_cause:
                    expected_layer = f.layer
                    break
            
            detected_layer = attribution.get("primary_layer")
            if expected_layer and detected_layer == expected_layer:
                warnings.append(f"cause_variant_same_layer: expected {expected_cause}, got {detected_cause}")
            else:
                errors.append(f"cause_mismatch: expected {expected_cause}, got {detected_cause}")
        
        # Check 2: Confidence is reasonable
        confidence = attribution.get("confidence", 0.0)
        if confidence < 0.5:
            warnings.append(f"low_confidence: {confidence}")
        
        # Check 3: Layer weights sum to 1
        layer_weights = attribution.get("layer_blame_weights", {})
        weight_sum = sum(layer_weights.values())
        if layer_weights and abs(weight_sum - 1.0) > 0.01:
            errors.append(f"weights_not_normalized: sum={weight_sum}")
        
        # Check 4: No equal blame (unless truly equal in injection)
        expected_weights = self.get_expected_layer_weights(run_id)
        if len(expected_weights) > 1:
            weight_values = list(layer_weights.values())
            if len(weight_values) > 1 and len(set(round(w, 2) for w in weight_values)) == 1:
                # All weights are equal
                if len(set(round(w, 2) for w in expected_weights.values())) != 1:
                    errors.append("blame_split_equally_when_not_expected")
        
        # Check 5: Excluded layers are documented
        excluded = attribution.get("excluded_layers", [])
        if not isinstance(excluded, list):
            warnings.append("excluded_layers_not_list")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "expected_cause": expected_cause,
            "detected_cause": detected_cause,
            "expected_weights": expected_weights,
            "detected_weights": layer_weights
        }
    
    def _save_plan(self, plan: InjectionPlan) -> None:
        """Save injection plan to artifact."""
        injection_dir = os.path.join(self.artifacts_dir, "testing", "injections")
        os.makedirs(injection_dir, exist_ok=True)
        
        path = os.path.join(injection_dir, f"{plan.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)


def simulate_run_with_injection(
    run_id: str,
    injector: FailureInjector,
    failure_types: List[FailureType],
    seed: int = 42
) -> Dict[str, Any]:
    """
    Simulate a run with injected failures and generate attribution.
    
    Returns simulated run result with attribution artifact.
    """
    # Create injection plan
    plan = injector.create_injection_plan(run_id, failure_types, seed)
    
    # Simulate execution steps (includes all possible layers)
    layers = ["tool", "retrieval", "evidence", "prompt", "generation", "planner", "environment"]
    execution_trace = []
    failures_triggered = []
    
    # Build layer -> failures map from plan
    layer_failures = {}
    for failure in plan.failures:
        layer_failures[failure.layer] = failure
    
    for step, layer in enumerate(layers):
        # Check if this layer has an injection
        injection = layer_failures.get(layer)
        
        step_result = {
            "step": step,
            "layer": layer,
            "success": injection is None,
            "injection": injection.to_dict() if injection else None
        }
        execution_trace.append(step_result)
        
        if injection:
            failures_triggered.append(injection)
    
    # Generate attribution based on injections
    if not failures_triggered:
        attribution = {
            "run_id": run_id,
            "failure": False,
            "primary_cause": None,
            "primary_layer": None,
            "confidence": 1.0,
            "layer_blame_weights": {},
            "excluded_layers": layers,
            "supporting_signals": {},
            "timestamp": datetime.now().isoformat(),
            "schema_version": "1.0"
        }
    else:
        # Calculate blame weights
        total_severity = sum(f.severity for f in failures_triggered)
        layer_weights: Dict[str, float] = {}
        for f in failures_triggered:
            w = f.severity / total_severity if total_severity > 0 else 1.0 / len(failures_triggered)
            layer_weights[f.layer] = layer_weights.get(f.layer, 0.0) + w
        
        # Primary cause is highest severity failure
        primary = max(failures_triggered, key=lambda f: (f.severity, -f.inject_at_step))
        
        # Excluded layers
        triggered_layers = {f.layer for f in failures_triggered}
        excluded = [l for l in layers if l not in triggered_layers]
        
        attribution = {
            "run_id": run_id,
            "failure": True,
            "primary_cause": primary.failure_type.value,
            "primary_layer": primary.layer,
            "confidence": min(0.95, 0.7 + 0.1 * len(failures_triggered)),
            "layer_blame_weights": layer_weights,
            "excluded_layers": excluded,
            "supporting_signals": {
                "injection_tags": [f.to_tag() for f in failures_triggered],
                "trace_steps": len(execution_trace)
            },
            "injected_failure": [f.to_dict() for f in failures_triggered],
            "timestamp": datetime.now().isoformat(),
            "schema_version": "1.0"
        }
    
    # Save attribution artifact
    attr_dir = os.path.join(injector.artifacts_dir, "attribution")
    os.makedirs(attr_dir, exist_ok=True)
    attr_path = os.path.join(attr_dir, f"{run_id}.json")
    with open(attr_path, "w", encoding="utf-8") as f:
        json.dump(attribution, f, indent=2, ensure_ascii=False)
    
    return {
        "run_id": run_id,
        "success": not failures_triggered,
        "execution_trace": execution_trace,
        "attribution": attribution,
        "attribution_path": attr_path
    }

