"""
Prompt Injection Guard: Detect and prevent prompt injection attacks.
Implements explicit rules for input sanitization and detection.
"""
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class InjectionPattern:
    """Pattern for detecting prompt injection."""
    pattern_id: str
    pattern_type: str  # regex, keyword, semantic
    pattern: str
    severity: str  # low, medium, high, critical
    description: str
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GuardDecision:
    """Result of prompt guard check."""
    safe: bool
    run_id: str
    input_hash: str
    
    # Detected issues
    detections: List[Dict[str, Any]] = field(default_factory=list)
    
    # Actions taken
    actions: List[str] = field(default_factory=list)
    
    # Sanitized input (if applicable)
    sanitized_input: Optional[str] = None
    
    # Metadata
    checked_at: str = ""
    schema_version: str = "1.0"
    
    def __post_init__(self):
        if not self.checked_at:
            self.checked_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PromptGuard:
    """
    Prompt injection detection and prevention.
    
    Features:
    - Pattern-based detection
    - Keyword blacklisting
    - Input sanitization
    - Audit logging
    """
    
    # Default patterns
    DEFAULT_PATTERNS = [
        InjectionPattern(
            pattern_id="ignore_instructions",
            pattern_type="regex",
            pattern=r"ignore\s+(all\s+)?(previous\s+)?instructions",
            severity="critical",
            description="Attempt to override instructions"
        ),
        InjectionPattern(
            pattern_id="system_prompt_leak",
            pattern_type="regex",
            pattern=r"(show|print|reveal|output)\s+(your\s+)?(system\s+)?(prompt|instructions)",
            severity="high",
            description="Attempt to leak system prompt"
        ),
        InjectionPattern(
            pattern_id="role_override",
            pattern_type="regex",
            pattern=r"you\s+are\s+(now\s+)?(a|an|the)\s+\w+",
            severity="medium",
            description="Attempt to override role"
        ),
        InjectionPattern(
            pattern_id="jailbreak_attempt",
            pattern_type="keyword",
            pattern="jailbreak|DAN|do anything now|bypass|hack",
            severity="critical",
            description="Known jailbreak keywords"
        ),
        InjectionPattern(
            pattern_id="code_injection",
            pattern_type="regex",
            pattern=r"```\s*(python|bash|shell|exec|eval)",
            severity="high",
            description="Potential code injection"
        ),
        InjectionPattern(
            pattern_id="delimiter_attack",
            pattern_type="regex",
            pattern=r"(###|---|===|\*\*\*)\s*(system|instruction|admin)",
            severity="high",
            description="Delimiter-based attack"
        ),
        InjectionPattern(
            pattern_id="encoding_attack",
            pattern_type="regex",
            pattern=r"(base64|rot13|unicode|hex)\s*(decode|encode)",
            severity="medium",
            description="Encoding-based evasion"
        ),
        InjectionPattern(
            pattern_id="prompt_leak_indirect",
            pattern_type="regex",
            pattern=r"(repeat|echo|say)\s+(everything|all|what)\s+(above|before|earlier)",
            severity="high",
            description="Indirect prompt leak attempt"
        )
    ]
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.guard_dir = os.path.join(artifacts_dir, "governance", "prompt_guard")
        os.makedirs(self.guard_dir, exist_ok=True)
        
        self._patterns: List[InjectionPattern] = list(self.DEFAULT_PATTERNS)
        self._decisions: List[GuardDecision] = []
    
    def add_pattern(self, pattern: InjectionPattern) -> None:
        """Add a detection pattern."""
        self._patterns.append(pattern)
    
    def check_input(
        self,
        run_id: str,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> GuardDecision:
        """
        Check user input for prompt injection.
        
        Args:
            run_id: Run identifier
            user_input: User input to check
            context: Optional context
            
        Returns:
            GuardDecision
        """
        import hashlib
        
        input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
        detections = []
        actions = []
        
        input_lower = user_input.lower()
        
        for pattern in self._patterns:
            if not pattern.enabled:
                continue
            
            detected = False
            
            if pattern.pattern_type == "regex":
                if re.search(pattern.pattern, input_lower, re.IGNORECASE):
                    detected = True
            elif pattern.pattern_type == "keyword":
                keywords = [k.strip().lower() for k in pattern.pattern.split("|")]
                if any(kw in input_lower for kw in keywords):
                    detected = True
            
            if detected:
                detections.append({
                    "pattern_id": pattern.pattern_id,
                    "severity": pattern.severity,
                    "description": pattern.description
                })
        
        # Determine safety
        critical_count = sum(1 for d in detections if d["severity"] == "critical")
        high_count = sum(1 for d in detections if d["severity"] == "high")
        
        safe = critical_count == 0 and high_count < 2
        
        # Determine actions
        if not safe:
            actions.append("block")
        elif detections:
            actions.append("warn")
            actions.append("sanitize")
        
        # Sanitize if needed
        sanitized = None
        if "sanitize" in actions:
            sanitized = self._sanitize_input(user_input)
        
        decision = GuardDecision(
            safe=safe,
            run_id=run_id,
            input_hash=input_hash,
            detections=detections,
            actions=actions,
            sanitized_input=sanitized
        )
        
        self._log_decision(decision)
        return decision
    
    def _sanitize_input(self, user_input: str) -> str:
        """Sanitize user input."""
        sanitized = user_input
        
        # Remove common injection patterns
        sanitized = re.sub(r"ignore\s+.*?instructions", "[REMOVED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"you\s+are\s+now\s+.*?\.", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"```\s*python.*?```", "[CODE REMOVED]", sanitized, flags=re.DOTALL)
        
        return sanitized.strip()
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        total = len(self._decisions)
        blocked = sum(1 for d in self._decisions if not d.safe)
        
        severity_counts: Dict[str, int] = {}
        for decision in self._decisions:
            for detection in decision.detections:
                sev = detection["severity"]
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            "total_checks": total,
            "blocked": blocked,
            "block_rate": blocked / total if total > 0 else 0.0,
            "severity_distribution": severity_counts
        }
    
    def _log_decision(self, decision: GuardDecision) -> None:
        """Log a guard decision."""
        self._decisions.append(decision)
        
        # Trim
        if len(self._decisions) > 10000:
            self._decisions = self._decisions[-10000:]
        
        # Save artifact
        path = os.path.join(self.guard_dir, f"{decision.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2, ensure_ascii=False)

