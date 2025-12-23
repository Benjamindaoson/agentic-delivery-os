"""
Governance Controller: Industrial-Grade Security and Cost Control
Features:
- AST-based prompt injection detection
- Structured security analysis
- Real cost guardrail enforcement
- Audit trail generation
"""
import re
import ast
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class ThreatLevel(str, Enum):
    """Security threat levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of security threats"""
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    DATA_EXFILTRATION = "data_exfiltration"
    SYSTEM_MANIPULATION = "system_manipulation"
    MALICIOUS_CODE = "malicious_code"
    RESOURCE_ABUSE = "resource_abuse"


@dataclass
class SecurityThreat:
    """Detected security threat"""
    threat_type: ThreatType
    threat_level: ThreatLevel
    description: str
    evidence: str
    location: str
    mitigation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "threat_type": self.threat_type.value,
            "threat_level": self.threat_level.value
        }


@dataclass
class SecurityAnalysisResult:
    """Result of security analysis"""
    is_safe: bool
    overall_threat_level: ThreatLevel
    threats: List[SecurityThreat] = field(default_factory=list)
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    analysis_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "overall_threat_level": self.overall_threat_level.value,
            "threats": [t.to_dict() for t in self.threats],
            "analyzed_at": self.analyzed_at,
            "analysis_time_ms": self.analysis_time_ms
        }


class PromptSecurityAnalyzer:
    """
    AST-based and pattern-based prompt security analyzer.
    Detects various injection and manipulation attempts.
    """
    
    # Prompt injection patterns (categorized by severity)
    INJECTION_PATTERNS = {
        ThreatLevel.CRITICAL: [
            # Direct instruction override
            r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
            r"(?i)disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
            r"(?i)forget\s+(everything|all)\s+(you\s+)?know",
            # System prompt extraction
            r"(?i)what\s+(is|are)\s+your\s+(system\s+)?prompt",
            r"(?i)reveal\s+(your\s+)?(system\s+)?instructions?",
            r"(?i)show\s+(me\s+)?(your\s+)?hidden\s+prompt",
        ],
        ThreatLevel.HIGH: [
            # Role manipulation
            r"(?i)you\s+are\s+now\s+(a\s+)?DAN",
            r"(?i)pretend\s+(you\s+are|to\s+be)\s+(a\s+)?different",
            r"(?i)act\s+as\s+(if\s+you\s+were|a)\s+jailbroken",
            # Instruction injection
            r"(?i)\[system\]|\[SYSTEM\]|\[System\]",
            r"(?i)\[instruction\]|\[INSTRUCTION\]",
            r"(?i)new\s+instructions?\s*:",
        ],
        ThreatLevel.MEDIUM: [
            # Boundary testing
            r"(?i)ignore\s+the\s+rules",
            r"(?i)break\s+(character|persona)",
            r"(?i)developer\s+mode",
            r"(?i)bypass\s+(the\s+)?(filter|restriction|limit)",
        ],
        ThreatLevel.LOW: [
            # Suspicious patterns
            r"(?i)hypothetically",
            r"(?i)in\s+theory",
            r"(?i)for\s+(educational|research)\s+purposes",
        ]
    }
    
    # Jailbreak patterns
    JAILBREAK_PATTERNS = [
        r"(?i)DAN\s*(mode|prompt)?",
        r"(?i)do\s+anything\s+now",
        r"(?i)no\s+restrictions?",
        r"(?i)unrestricted\s+mode",
        r"(?i)evil\s+(mode|assistant|bot)",
    ]
    
    # Code execution patterns (for code-containing prompts)
    MALICIOUS_CODE_PATTERNS = [
        r"(?i)(exec|eval)\s*\(",
        r"(?i)__import__\s*\(",
        r"(?i)os\.(system|popen|exec)",
        r"(?i)subprocess\.(call|run|Popen)",
        r"(?i)rm\s+-rf",
        r"(?i)(curl|wget)\s+.*\|\s*(bash|sh)",
    ]
    
    @classmethod
    def analyze(cls, text: str, context: Optional[Dict[str, Any]] = None) -> SecurityAnalysisResult:
        """
        Analyze text for security threats.
        
        Args:
            text: Text to analyze (could be user input, prompt, etc.)
            context: Optional context for analysis
            
        Returns:
            SecurityAnalysisResult with detected threats
        """
        import time
        start_time = time.time()
        
        threats: List[SecurityThreat] = []
        
        # 1. Pattern-based injection detection
        injection_threats = cls._detect_injection_patterns(text)
        threats.extend(injection_threats)
        
        # 2. Jailbreak detection
        jailbreak_threats = cls._detect_jailbreak(text)
        threats.extend(jailbreak_threats)
        
        # 3. Code security analysis (if text contains code-like content)
        if cls._looks_like_code(text):
            code_threats = cls._analyze_code_security(text)
            threats.extend(code_threats)
        
        # 4. Structural analysis
        structural_threats = cls._structural_analysis(text)
        threats.extend(structural_threats)
        
        # Determine overall threat level
        if not threats:
            overall_level = ThreatLevel.NONE
        else:
            threat_levels = [t.threat_level for t in threats]
            if ThreatLevel.CRITICAL in threat_levels:
                overall_level = ThreatLevel.CRITICAL
            elif ThreatLevel.HIGH in threat_levels:
                overall_level = ThreatLevel.HIGH
            elif ThreatLevel.MEDIUM in threat_levels:
                overall_level = ThreatLevel.MEDIUM
            else:
                overall_level = ThreatLevel.LOW
        
        is_safe = overall_level in [ThreatLevel.NONE, ThreatLevel.LOW]
        
        analysis_time = (time.time() - start_time) * 1000
        
        return SecurityAnalysisResult(
            is_safe=is_safe,
            overall_threat_level=overall_level,
            threats=threats,
            analysis_time_ms=analysis_time
        )
    
    @classmethod
    def _detect_injection_patterns(cls, text: str) -> List[SecurityThreat]:
        """Detect prompt injection patterns"""
        threats = []
        
        for level, patterns in cls.INJECTION_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    threats.append(SecurityThreat(
                        threat_type=ThreatType.PROMPT_INJECTION,
                        threat_level=level,
                        description=f"Prompt injection pattern detected: {pattern[:50]}",
                        evidence=match.group()[:100],
                        location=f"Position {match.start()}-{match.end()}",
                        mitigation="Sanitize input or reject request"
                    ))
        
        return threats
    
    @classmethod
    def _detect_jailbreak(cls, text: str) -> List[SecurityThreat]:
        """Detect jailbreak attempts"""
        threats = []
        
        for pattern in cls.JAILBREAK_PATTERNS:
            if re.search(pattern, text):
                threats.append(SecurityThreat(
                    threat_type=ThreatType.JAILBREAK_ATTEMPT,
                    threat_level=ThreatLevel.HIGH,
                    description="Jailbreak attempt detected",
                    evidence=re.search(pattern, text).group()[:100],
                    location="Full text",
                    mitigation="Block request and log for review"
                ))
        
        return threats
    
    @classmethod
    def _looks_like_code(cls, text: str) -> bool:
        """Check if text contains code-like content"""
        code_indicators = [
            r"def\s+\w+\s*\(",
            r"import\s+\w+",
            r"class\s+\w+",
            r"function\s+\w+",
            r"\{\s*\n",
            r"```\w*\n",
        ]
        return any(re.search(p, text) for p in code_indicators)
    
    @classmethod
    def _analyze_code_security(cls, text: str) -> List[SecurityThreat]:
        """Analyze code content for security issues"""
        threats = []
        
        # Pattern-based detection
        for pattern in cls.MALICIOUS_CODE_PATTERNS:
            if re.search(pattern, text):
                threats.append(SecurityThreat(
                    threat_type=ThreatType.MALICIOUS_CODE,
                    threat_level=ThreatLevel.HIGH,
                    description="Potentially malicious code pattern detected",
                    evidence=re.search(pattern, text).group()[:100],
                    location="Code content",
                    mitigation="Do not execute; review manually"
                ))
        
        # Try AST analysis for Python code
        try:
            # Extract Python code blocks
            code_blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
            for code_block in code_blocks:
                ast_threats = cls._ast_analyze_python(code_block)
                threats.extend(ast_threats)
        except Exception:
            pass
        
        return threats
    
    @classmethod
    def _ast_analyze_python(cls, code: str) -> List[SecurityThreat]:
        """AST-based Python code analysis"""
        threats = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Check for dangerous calls
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    dangerous_funcs = ["exec", "eval", "compile", "__import__"]
                    if func_name in dangerous_funcs:
                        threats.append(SecurityThreat(
                            threat_type=ThreatType.MALICIOUS_CODE,
                            threat_level=ThreatLevel.CRITICAL,
                            description=f"Dangerous function call: {func_name}",
                            evidence=f"{func_name}() call detected via AST",
                            location=f"Line {node.lineno}",
                            mitigation="Remove dangerous function call"
                        ))
                
                # Check for suspicious imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    dangerous_modules = ["os", "subprocess", "sys", "socket", "requests"]
                    module_name = ""
                    if isinstance(node, ast.Import):
                        module_name = node.names[0].name.split(".")[0]
                    else:
                        module_name = node.module.split(".")[0] if node.module else ""
                    
                    if module_name in dangerous_modules:
                        threats.append(SecurityThreat(
                            threat_type=ThreatType.MALICIOUS_CODE,
                            threat_level=ThreatLevel.MEDIUM,
                            description=f"Potentially dangerous import: {module_name}",
                            evidence=f"import {module_name}",
                            location=f"Line {node.lineno}",
                            mitigation="Review import necessity"
                        ))
        
        except SyntaxError:
            pass  # Not valid Python, skip AST analysis
        
        return threats
    
    @classmethod
    def _structural_analysis(cls, text: str) -> List[SecurityThreat]:
        """Structural analysis for suspicious patterns"""
        threats = []
        
        # Check for unusual character sequences (potential encoding attacks)
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
            threats.append(SecurityThreat(
                threat_type=ThreatType.SYSTEM_MANIPULATION,
                threat_level=ThreatLevel.MEDIUM,
                description="Control characters detected",
                evidence="Non-printable characters in input",
                location="Full text",
                mitigation="Sanitize input"
            ))
        
        # Check for excessive length (potential DoS)
        if len(text) > 50000:
            threats.append(SecurityThreat(
                threat_type=ThreatType.RESOURCE_ABUSE,
                threat_level=ThreatLevel.MEDIUM,
                description="Excessively long input",
                evidence=f"Input length: {len(text)} characters",
                location="Full text",
                mitigation="Truncate or reject input"
            ))
        
        return threats


@dataclass
class CostGuardrailResult:
    """Result of cost guardrail check"""
    allowed: bool
    current_cost: float
    budget_limit: float
    remaining_budget: float
    utilization_rate: float
    warning_level: str  # none, soft, hard
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CostGuardrail:
    """
    Real cost guardrail enforcement.
    Tracks costs and enforces budget limits.
    """
    
    def __init__(
        self,
        artifacts_base: str = "artifacts",
        default_budget: float = 100.0,
        soft_limit_ratio: float = 0.8,
        hard_limit_ratio: float = 1.0
    ):
        self.artifacts_base = artifacts_base
        self.default_budget = default_budget
        self.soft_limit_ratio = soft_limit_ratio
        self.hard_limit_ratio = hard_limit_ratio
    
    def check(
        self,
        task_id: str,
        budget_limit: Optional[float] = None,
        estimated_cost: float = 0.0
    ) -> CostGuardrailResult:
        """
        Check if operation is allowed under budget.
        
        Args:
            task_id: Task ID
            budget_limit: Budget limit (or use default)
            estimated_cost: Estimated cost of upcoming operation
            
        Returns:
            CostGuardrailResult
        """
        limit = budget_limit or self.default_budget
        current_cost = self._get_current_cost(task_id)
        
        # Calculate projected cost
        projected_cost = current_cost + estimated_cost
        remaining = max(0, limit - current_cost)
        utilization = current_cost / max(limit, 0.001)
        
        # Determine warning level and allowance
        if projected_cost >= limit * self.hard_limit_ratio:
            allowed = False
            warning_level = "hard"
            reason = f"Hard budget limit exceeded: {projected_cost:.4f} >= {limit * self.hard_limit_ratio:.4f}"
        elif projected_cost >= limit * self.soft_limit_ratio:
            allowed = True  # Allow but warn
            warning_level = "soft"
            reason = f"Approaching budget limit: {projected_cost:.4f} >= {limit * self.soft_limit_ratio:.4f}"
        else:
            allowed = True
            warning_level = "none"
            reason = "Within budget"
        
        return CostGuardrailResult(
            allowed=allowed,
            current_cost=current_cost,
            budget_limit=limit,
            remaining_budget=remaining,
            utilization_rate=utilization,
            warning_level=warning_level,
            reason=reason
        )
    
    def _get_current_cost(self, task_id: str) -> float:
        """Get current accumulated cost for task"""
        cost_path = os.path.join(
            self.artifacts_base, "rag_project", task_id, "cost_report.json"
        )
        
        if not os.path.exists(cost_path):
            return 0.0
        
        try:
            with open(cost_path, "r", encoding="utf-8") as f:
                entries = json.load(f) or []
            return sum(e.get("cost", e.get("estimated_cost", 0)) for e in entries)
        except Exception:
            return 0.0
    
    def record_cost(
        self,
        task_id: str,
        cost: float,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a cost event"""
        cost_dir = os.path.join(self.artifacts_base, "rag_project", task_id)
        os.makedirs(cost_dir, exist_ok=True)
        
        cost_path = os.path.join(cost_dir, "cost_report.json")
        
        # Load existing
        existing = []
        if os.path.exists(cost_path):
            try:
                with open(cost_path, "r", encoding="utf-8") as f:
                    existing = json.load(f) or []
            except Exception:
                existing = []
        
        # Add new entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "cost": cost,
            **(metadata or {})
        }
        existing.append(entry)
        
        # Save
        with open(cost_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)


class GovernanceController:
    """
    Industrial-grade governance controller.
    Combines security analysis and cost guardrails.
    """
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.security_analyzer = PromptSecurityAnalyzer()
        self.cost_guardrail = CostGuardrail(artifacts_base)
        self.artifacts_base = artifacts_base
    
    def check_request(
        self,
        task_id: str,
        user_input: str,
        budget_limit: Optional[float] = None,
        estimated_cost: float = 0.0,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive request check.
        
        Returns:
            Tuple of (allowed, details)
        """
        # 1. Security check
        security_result = self.security_analyzer.analyze(user_input, context)
        
        # 2. Cost check
        cost_result = self.cost_guardrail.check(task_id, budget_limit, estimated_cost)
        
        # 3. Determine overall allowance
        allowed = security_result.is_safe and cost_result.allowed
        
        # 4. Build details
        details = {
            "allowed": allowed,
            "security": security_result.to_dict(),
            "cost": cost_result.to_dict(),
            "checked_at": datetime.now().isoformat()
        }
        
        # 5. Save audit record
        self._save_audit_record(task_id, details)
        
        return allowed, details
    
    def _save_audit_record(self, task_id: str, details: Dict[str, Any]):
        """Save governance check to audit log"""
        audit_dir = os.path.join(self.artifacts_base, "governance", task_id)
        os.makedirs(audit_dir, exist_ok=True)
        
        # Append to audit log
        audit_path = os.path.join(audit_dir, "audit_log.jsonl")
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(details, ensure_ascii=False) + "\n")


# Singleton instances
_security_analyzer: Optional[PromptSecurityAnalyzer] = None
_cost_guardrail: Optional[CostGuardrail] = None
_governance_controller: Optional[GovernanceController] = None


def get_security_analyzer() -> PromptSecurityAnalyzer:
    """Get singleton PromptSecurityAnalyzer"""
    global _security_analyzer
    if _security_analyzer is None:
        _security_analyzer = PromptSecurityAnalyzer()
    return _security_analyzer


def get_cost_guardrail() -> CostGuardrail:
    """Get singleton CostGuardrail"""
    global _cost_guardrail
    if _cost_guardrail is None:
        _cost_guardrail = CostGuardrail()
    return _cost_guardrail


def get_governance_controller() -> GovernanceController:
    """Get singleton GovernanceController"""
    global _governance_controller
    if _governance_controller is None:
        _governance_controller = GovernanceController()
    return _governance_controller

