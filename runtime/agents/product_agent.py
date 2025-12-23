"""
Product Agent: Real Feasibility Judgment
Industrial-grade implementation with:
- Real feasibility assessment (proceed/revise/abort)
- Spec validation with clear criteria
- LLM-assisted analysis
- Clear decision rationale
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple, List, Optional
from enum import Enum
import json
import re
from datetime import datetime
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader


class FeasibilityDecision(str, Enum):
    """Feasibility decisions"""
    PROCEED = "proceed"    # Go ahead with execution
    REVISE = "revise"      # Need clarification/changes
    ABORT = "abort"        # Cannot proceed


class SpecValidationResult:
    """Result of spec validation"""
    
    def __init__(
        self,
        is_valid: bool,
        decision: FeasibilityDecision,
        completeness_score: float,
        clarity_score: float,
        feasibility_score: float,
        missing_required: List[str],
        ambiguous_fields: List[str],
        blockers: List[str],
        warnings: List[str],
        suggestions: List[str]
    ):
        self.is_valid = is_valid
        self.decision = decision
        self.completeness_score = completeness_score
        self.clarity_score = clarity_score
        self.feasibility_score = feasibility_score
        self.missing_required = missing_required
        self.ambiguous_fields = ambiguous_fields
        self.blockers = blockers
        self.warnings = warnings
        self.suggestions = suggestions
    
    @property
    def overall_score(self) -> float:
        return (self.completeness_score + self.clarity_score + self.feasibility_score) / 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "decision": self.decision.value,
            "completeness_score": self.completeness_score,
            "clarity_score": self.clarity_score,
            "feasibility_score": self.feasibility_score,
            "overall_score": self.overall_score,
            "missing_required": self.missing_required,
            "ambiguous_fields": self.ambiguous_fields,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "suggestions": self.suggestions
        }


class SpecValidator:
    """Validates specs against required criteria"""
    
    # Required fields for different spec types
    REQUIRED_FIELDS = {
        "rag": ["goal", "data_sources"],
        "chat": ["goal"],
        "analysis": ["goal", "data_sources"],
        "default": ["goal"]
    }
    
    # Fields that indicate better quality
    QUALITY_FIELDS = [
        "success_criteria",
        "constraints",
        "audience",
        "expected_output",
        "budget",
        "deadline"
    ]
    
    @classmethod
    def validate(cls, spec: Dict[str, Any]) -> SpecValidationResult:
        """
        Validate a spec and return detailed result.
        
        Validation checks:
        1. Required fields present
        2. Fields are non-empty
        3. No obviously invalid values
        4. Identify ambiguous or unclear content
        """
        # Determine spec type
        spec_type = spec.get("type", "default")
        required = cls.REQUIRED_FIELDS.get(spec_type, cls.REQUIRED_FIELDS["default"])
        
        # Track issues
        missing_required = []
        ambiguous_fields = []
        blockers = []
        warnings = []
        suggestions = []
        
        # 1. Check required fields
        for field in required:
            if field not in spec:
                missing_required.append(field)
            elif cls._is_empty(spec[field]):
                missing_required.append(f"{field} (empty)")
        
        # 2. Check field quality
        for field, value in spec.items():
            issues = cls._check_field_quality(field, value)
            ambiguous_fields.extend(issues.get("ambiguous", []))
            warnings.extend(issues.get("warnings", []))
        
        # 3. Check for blocking issues
        blockers.extend(cls._check_blockers(spec))
        
        # 4. Generate suggestions
        for field in cls.QUALITY_FIELDS:
            if field not in spec:
                suggestions.append(f"Consider adding '{field}' for better results")
        
        # Calculate scores
        completeness_score = cls._calculate_completeness(spec, required)
        clarity_score = cls._calculate_clarity(spec, ambiguous_fields)
        feasibility_score = cls._calculate_feasibility(spec, blockers)
        
        # Determine decision
        if blockers:
            decision = FeasibilityDecision.ABORT
            is_valid = False
        elif missing_required or len(ambiguous_fields) > 2:
            decision = FeasibilityDecision.REVISE
            is_valid = False
        else:
            decision = FeasibilityDecision.PROCEED
            is_valid = True
        
        return SpecValidationResult(
            is_valid=is_valid,
            decision=decision,
            completeness_score=completeness_score,
            clarity_score=clarity_score,
            feasibility_score=feasibility_score,
            missing_required=missing_required,
            ambiguous_fields=ambiguous_fields,
            blockers=blockers,
            warnings=warnings,
            suggestions=suggestions
        )
    
    @classmethod
    def _is_empty(cls, value: Any) -> bool:
        """Check if a value is effectively empty"""
        if value is None:
            return True
        if isinstance(value, str) and len(value.strip()) == 0:
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False
    
    @classmethod
    def _check_field_quality(cls, field: str, value: Any) -> Dict[str, List[str]]:
        """Check quality of a specific field"""
        issues = {"ambiguous": [], "warnings": []}
        
        if isinstance(value, str):
            # Check for vague language
            vague_patterns = [
                r"\betc\.?\b",
                r"\band so on\b",
                r"\bsomething like\b",
                r"\bmaybe\b",
                r"\bpossibly\b"
            ]
            for pattern in vague_patterns:
                if re.search(pattern, value, re.IGNORECASE):
                    issues["ambiguous"].append(f"{field}: contains vague language")
                    break
            
            # Check for too short content
            if field in ["goal", "description"] and len(value) < 10:
                issues["warnings"].append(f"{field}: very short, may need more detail")
        
        return issues
    
    @classmethod
    def _check_blockers(cls, spec: Dict[str, Any]) -> List[str]:
        """Check for blocking issues"""
        blockers = []
        
        # Check for obviously infeasible constraints
        budget = spec.get("budget", {})
        if isinstance(budget, dict):
            max_cost = budget.get("max_cost", float("inf"))
            if max_cost <= 0:
                blockers.append("Budget is zero or negative")
        
        # Check for empty goal
        goal = spec.get("goal", "")
        if isinstance(goal, str) and len(goal.strip()) < 3:
            blockers.append("Goal is not specified or too vague")
        
        # Check for obviously impossible deadlines
        deadline = spec.get("deadline")
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
                if deadline_dt < datetime.now(deadline_dt.tzinfo):
                    blockers.append("Deadline is in the past")
            except Exception:
                pass
        
        return blockers
    
    @classmethod
    def _calculate_completeness(cls, spec: Dict[str, Any], required: List[str]) -> float:
        """Calculate completeness score"""
        if not required:
            return 1.0
        
        present = sum(1 for f in required if f in spec and not cls._is_empty(spec[f]))
        base_score = present / len(required)
        
        # Bonus for quality fields
        quality_present = sum(1 for f in cls.QUALITY_FIELDS if f in spec)
        bonus = min(quality_present * 0.05, 0.2)
        
        return min(base_score + bonus, 1.0)
    
    @classmethod
    def _calculate_clarity(cls, spec: Dict[str, Any], ambiguous: List[str]) -> float:
        """Calculate clarity score"""
        # Start with 1.0 and deduct for ambiguity
        score = 1.0
        score -= len(ambiguous) * 0.1
        return max(0.0, score)
    
    @classmethod
    def _calculate_feasibility(cls, spec: Dict[str, Any], blockers: List[str]) -> float:
        """Calculate feasibility score"""
        if blockers:
            return 0.0
        return 1.0


class ProductAgent(BaseAgent):
    """
    Real Product Agent with feasibility judgment.
    
    Responsibilities:
    - Validate spec completeness and clarity
    - Assess feasibility
    - Make proceed/revise/abort decisions
    - Generate clarification suggestions
    """
    
    def __init__(self):
        super().__init__("Product")
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
        self.validator = SpecValidator()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Execute feasibility assessment.
        
        Returns:
        - proceed: Ready to execute
        - revise: Need clarification/changes
        - abort: Cannot proceed due to blockers
        """
        spec = context.get("spec", {})
        
        # 1. Validate spec with engineering rules
        validation = self.validator.validate(spec)
        
        # 2. Get LLM analysis for additional insights
        llm_output, llm_meta = await self._call_llm_for_analysis(
            spec, task_id=task_id, tenant_id=context.get("tenant_id", "default")
        )
        
        # 3. Merge LLM insights if available
        if llm_meta.get("llm_used") and llm_output:
            # Add LLM-detected issues
            llm_ambiguous = llm_output.get("ambiguous_areas", [])
            llm_blockers = llm_output.get("blockers", [])
            llm_suggestions = llm_output.get("suggestions", [])
            
            # Update validation with LLM insights
            validation.ambiguous_fields.extend(llm_ambiguous[:3])
            validation.blockers.extend(llm_blockers[:2])
            validation.suggestions.extend(llm_suggestions[:3])
            
            # Re-evaluate decision if LLM found blockers
            if llm_blockers and validation.decision != FeasibilityDecision.ABORT:
                validation.decision = FeasibilityDecision.ABORT
                validation.is_valid = False
        
        # 4. Build decision and reason
        decision = validation.decision.value
        
        if validation.decision == FeasibilityDecision.PROCEED:
            reason = f"Spec 验证通过 (完整性: {validation.completeness_score:.2f}, 清晰度: {validation.clarity_score:.2f})"
        elif validation.decision == FeasibilityDecision.REVISE:
            issues = validation.missing_required + validation.ambiguous_fields
            reason = f"需要修订: {'; '.join(issues[:3])}"
        else:  # ABORT
            reason = f"无法继续: {'; '.join(validation.blockers[:2])}"
        
        # Add warnings if any
        if validation.warnings:
            reason += f" | 警告: {'; '.join(validation.warnings[:2])}"
        
        # 5. Build state update
        state_update = {
            "product_agent_executed": True,
            "spec_validated": validation.is_valid,
            "validation_result": validation.to_dict(),
            "feasibility_decision": decision
        }
        
        if llm_meta.get("llm_used") and llm_output:
            state_update["clarification_summary"] = llm_output.get("clarification_summary", "")
            state_update["inferred_constraints"] = llm_output.get("inferred_constraints", [])
            state_update["missing_fields"] = llm_output.get("missing_fields", [])
            state_update["assumptions"] = llm_output.get("assumptions", [])
        
        return {
            "decision": decision,
            "reason": reason,
            "validation_result": validation.to_dict(),
            "llm_result": llm_meta,
            "state_update": state_update
        }
    
    async def _call_llm_for_analysis(self, spec: Dict[str, Any], task_id: str = None, tenant_id: str = "default") -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """调用 LLM 进行 spec 分析"""
        prompt_data = self.prompt_loader.load_prompt("product", "spec_interpreter", "v1")
        
        # 构建 user prompt
        spec_str = json.dumps(spec, indent=2, ensure_ascii=False) if spec else "{}"
        user_prompt = prompt_data["user_prompt_template"].format(spec=spec_str)
        
        # 调用 LLM（使用新的 generate_json 接口）
        # 使用 adapter.call(...)，adapter 负责限流/重试/计费/trace 写入
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data["system_prompt"],
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=tenant_id,
            model=prompt_data.get("model", None)
        )
        
        return result, meta
    
    def get_governing_question(self) -> str:
        return "是否启动？需求是否清晰？"

