"""
Guards: Prompt injection guard, cost guardrail, safety checks.
Explicit rules for system safety.
"""
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class GuardResult:
    """Result of a guard check."""
    passed: bool
    guard_type: str
    reason: str
    severity: str = "low"  # low, medium, high, critical
    blocked_content: Optional[str] = None
    remediation: Optional[str] = None
    checked_at: str = ""
    
    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostGuardState:
    """State for cost guardrail."""
    session_id: str
    budget_limit: float
    spent: float = 0.0
    remaining: float = 0.0
    exceeded: bool = False
    run_count: int = 0
    last_updated: str = ""
    
    def __post_init__(self):
        self.remaining = self.budget_limit - self.spent
        self.exceeded = self.spent >= self.budget_limit
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PromptInjectionGuard:
    """
    Guards against prompt injection attacks.
    
    Explicit rules for detecting and blocking injection attempts.
    """
    
    # Injection patterns
    INJECTION_PATTERNS = [
        # Direct instruction overrides
        r"ignore\s+(previous|above|all)\s+instructions",
        r"disregard\s+(previous|above|all)\s+(instructions|prompts?)",
        r"forget\s+(everything|previous|above)",
        
        # System prompt extraction
        r"(what|show|tell)\s+(is|me)\s+(your|the)\s+(system|initial)\s+prompt",
        r"repeat\s+(your|the)\s+(system|initial)\s+prompt",
        r"print\s+(your|the)\s+(system|initial)\s+prompt",
        
        # Role manipulation
        r"you\s+are\s+now\s+",
        r"pretend\s+(to\s+be|you\s+are)\s+",
        r"act\s+as\s+if\s+you\s+",
        
        # Jailbreak attempts
        r"(DAN|jailbreak|bypass)\s+mode",
        r"developer\s+mode\s+enabled",
        
        # Code execution attempts
        r"exec\s*\(",
        r"eval\s*\(",
        r"import\s+os",
        r"subprocess\.",
        r"__import__",
    ]
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.guard_dir = os.path.join(artifacts_dir, "governance", "guards")
        os.makedirs(self.guard_dir, exist_ok=True)
        
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
    
    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardResult:
        """
        Check content for prompt injection.
        
        Args:
            content: Content to check
            context: Optional context
            
        Returns:
            GuardResult
        """
        for pattern in self._compiled_patterns:
            match = pattern.search(content)
            if match:
                result = GuardResult(
                    passed=False,
                    guard_type="prompt_injection",
                    reason=f"Potential injection detected: {match.group()}",
                    severity="high",
                    blocked_content=match.group(),
                    remediation="Remove or rephrase the flagged content"
                )
                self._log_detection(content, result)
                return result
        
        return GuardResult(
            passed=True,
            guard_type="prompt_injection",
            reason="No injection patterns detected"
        )
    
    def sanitize(self, content: str) -> Tuple[str, List[str]]:
        """
        Sanitize content by removing injection patterns.
        
        Returns:
            Tuple of (sanitized_content, list of removed patterns)
        """
        removed = []
        sanitized = content
        
        for pattern in self._compiled_patterns:
            matches = pattern.findall(content)
            if matches:
                removed.extend(matches)
                sanitized = pattern.sub("[REDACTED]", sanitized)
        
        return sanitized, removed
    
    def _log_detection(self, content: str, result: GuardResult) -> None:
        """Log a detection."""
        log_path = os.path.join(self.guard_dir, "injection_log.jsonl")
        
        log_entry = {
            "content_preview": content[:200] if len(content) > 200 else content,
            "result": result.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")


class CostGuardrail:
    """
    Enforces cost limits across sessions.
    
    Provides:
    - Per-session budget tracking
    - Global budget tracking
    - Automatic blocking when exceeded
    """
    
    DEFAULT_SESSION_BUDGET = 10.0  # $10 per session
    DEFAULT_GLOBAL_DAILY_BUDGET = 100.0  # $100 per day
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.guard_dir = os.path.join(artifacts_dir, "governance", "guards")
        os.makedirs(self.guard_dir, exist_ok=True)
        
        self._session_states: Dict[str, CostGuardState] = {}
        self._global_spent_today = 0.0
        
        self._load_state()
    
    def check_budget(
        self,
        session_id: str,
        estimated_cost: float,
        budget_limit: Optional[float] = None
    ) -> GuardResult:
        """
        Check if a run is within budget.
        
        Args:
            session_id: Session identifier
            estimated_cost: Estimated cost for the run
            budget_limit: Optional custom budget limit
            
        Returns:
            GuardResult
        """
        budget = budget_limit or self.DEFAULT_SESSION_BUDGET
        
        # Get or create session state
        if session_id not in self._session_states:
            self._session_states[session_id] = CostGuardState(
                session_id=session_id,
                budget_limit=budget
            )
        
        state = self._session_states[session_id]
        
        # Check if already exceeded
        if state.exceeded:
            return GuardResult(
                passed=False,
                guard_type="cost_guardrail",
                reason=f"Session budget already exceeded: ${state.spent:.2f} of ${budget:.2f}",
                severity="critical"
            )
        
        # Check if this run would exceed
        if state.spent + estimated_cost > budget:
            return GuardResult(
                passed=False,
                guard_type="cost_guardrail",
                reason=f"Run would exceed budget: ${state.spent:.2f} + ${estimated_cost:.2f} > ${budget:.2f}",
                severity="high",
                remediation="Reduce run cost or increase budget"
            )
        
        # Check global daily budget
        if self._global_spent_today + estimated_cost > self.DEFAULT_GLOBAL_DAILY_BUDGET:
            return GuardResult(
                passed=False,
                guard_type="cost_guardrail",
                reason=f"Global daily budget would be exceeded",
                severity="critical"
            )
        
        return GuardResult(
            passed=True,
            guard_type="cost_guardrail",
            reason=f"Within budget: ${state.remaining:.2f} remaining"
        )
    
    def record_spend(
        self,
        session_id: str,
        cost: float,
        run_id: Optional[str] = None
    ) -> CostGuardState:
        """
        Record cost spent.
        
        Args:
            session_id: Session identifier
            cost: Cost incurred
            run_id: Optional run ID for tracking
            
        Returns:
            Updated CostGuardState
        """
        if session_id not in self._session_states:
            self._session_states[session_id] = CostGuardState(
                session_id=session_id,
                budget_limit=self.DEFAULT_SESSION_BUDGET
            )
        
        state = self._session_states[session_id]
        state.spent += cost
        state.remaining = state.budget_limit - state.spent
        state.exceeded = state.spent >= state.budget_limit
        state.run_count += 1
        state.last_updated = datetime.now().isoformat()
        
        self._global_spent_today += cost
        
        self._save_state()
        
        return state
    
    def get_session_state(self, session_id: str) -> Optional[CostGuardState]:
        """Get session cost state."""
        return self._session_states.get(session_id)
    
    def reset_session(self, session_id: str) -> None:
        """Reset session budget."""
        if session_id in self._session_states:
            budget = self._session_states[session_id].budget_limit
            self._session_states[session_id] = CostGuardState(
                session_id=session_id,
                budget_limit=budget
            )
            self._save_state()
    
    def _save_state(self) -> None:
        """Save state to file."""
        path = os.path.join(self.guard_dir, "cost_state.json")
        
        state = {
            "sessions": {
                sid: s.to_dict() for sid, s in self._session_states.items()
            },
            "global_spent_today": self._global_spent_today,
            "last_updated": datetime.now().isoformat()
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _load_state(self) -> None:
        """Load state from file."""
        path = os.path.join(self.guard_dir, "cost_state.json")
        
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            for sid, sdata in state.get("sessions", {}).items():
                self._session_states[sid] = CostGuardState(**sdata)
            
            self._global_spent_today = state.get("global_spent_today", 0.0)
        except (json.JSONDecodeError, IOError):
            pass


class SafetyGuard:
    """
    General safety checks for content.
    """
    
    # Sensitive content patterns
    SENSITIVE_PATTERNS = [
        r"\b(ssn|social\s+security)\b.*\d{3}-\d{2}-\d{4}",
        r"\b(credit\s+card|cc)\b.*\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
        r"\b(password|pwd|secret)\s*[:=]\s*\S+",
        r"\b(api[_-]?key|token)\s*[:=]\s*\S+",
    ]
    
    def __init__(self):
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS
        ]
    
    def check_sensitive_data(self, content: str) -> GuardResult:
        """Check for sensitive data leakage."""
        for pattern in self._compiled_patterns:
            if pattern.search(content):
                return GuardResult(
                    passed=False,
                    guard_type="sensitive_data",
                    reason="Potential sensitive data detected",
                    severity="high",
                    remediation="Remove or redact sensitive information"
                )
        
        return GuardResult(
            passed=True,
            guard_type="sensitive_data",
            reason="No sensitive data patterns detected"
        )
    
    def check_output_length(
        self,
        content: str,
        max_length: int = 10000
    ) -> GuardResult:
        """Check output length."""
        if len(content) > max_length:
            return GuardResult(
                passed=False,
                guard_type="output_length",
                reason=f"Output too long: {len(content)} > {max_length}",
                severity="medium"
            )
        
        return GuardResult(
            passed=True,
            guard_type="output_length",
            reason=f"Output length OK: {len(content)}"
        )


class GuardOrchestrator:
    """
    Orchestrates all guards for comprehensive checking.
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.injection_guard = PromptInjectionGuard(artifacts_dir)
        self.cost_guardrail = CostGuardrail(artifacts_dir)
        self.safety_guard = SafetyGuard()
    
    def check_input(
        self,
        content: str,
        session_id: str,
        estimated_cost: float = 0.0
    ) -> Dict[str, GuardResult]:
        """
        Run all input guards.
        
        Returns:
            Dict of guard_type -> GuardResult
        """
        results = {}
        
        # Check injection
        results["prompt_injection"] = self.injection_guard.check(content)
        
        # Check cost
        if estimated_cost > 0:
            results["cost"] = self.cost_guardrail.check_budget(session_id, estimated_cost)
        
        # Check sensitive data
        results["sensitive_data"] = self.safety_guard.check_sensitive_data(content)
        
        return results
    
    def check_output(self, content: str) -> Dict[str, GuardResult]:
        """
        Run all output guards.
        
        Returns:
            Dict of guard_type -> GuardResult
        """
        results = {}
        
        results["sensitive_data"] = self.safety_guard.check_sensitive_data(content)
        results["output_length"] = self.safety_guard.check_output_length(content)
        
        return results
    
    def all_passed(self, results: Dict[str, GuardResult]) -> bool:
        """Check if all guards passed."""
        return all(r.passed for r in results.values())
    
    def get_blocking_guards(
        self,
        results: Dict[str, GuardResult]
    ) -> List[GuardResult]:
        """Get guards that blocked."""
        return [r for r in results.values() if not r.passed]



