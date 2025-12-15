"""
Governance Engine: 系统级治理决策引擎
基于规则进行系统级决策，不依赖 LLM
"""
from typing import List, Dict, Any, Optional
from enum import Enum
from runtime.governance.agent_report import AgentExecutionReport, RiskLevel, AgentStatus
from runtime.governance.conflict_detector import ConflictDetector, Conflict, ConflictSeverity

class ExecutionMode(str, Enum):
    """执行模式"""
    NORMAL = "normal"  # 正常执行
    DEGRADED = "degraded"  # 降级执行
    MINIMAL = "minimal"  # 最小执行
    PAUSED = "paused"  # 暂停等待人工介入

class GovernanceDecision:
    """系统级治理决策"""
    def __init__(
        self,
        execution_mode: ExecutionMode,
        restrictions: List[str],
        reasoning: str,
        conflicts: List[Conflict],
        metrics: Dict[str, Any]
    ):
        self.execution_mode = execution_mode
        self.restrictions = restrictions
        self.reasoning = reasoning
        self.conflicts = conflicts
        self.metrics = metrics
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode.value,
            "restrictions": self.restrictions,
            "reasoning": self.reasoning,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "metrics": self.metrics
        }

class GovernanceEngine:
    """治理引擎：基于规则进行系统级决策"""
    
    def __init__(self):
        self.conflict_detector = ConflictDetector()
    
    def make_decision(
        self,
        reports: List[AgentExecutionReport],
        total_cost: float = 0.0,
        budget_limit: float = 1000.0,
        llm_fallback_count: int = 0
    ) -> GovernanceDecision:
        """
        基于 Agent 报告进行系统级治理决策
        
        决策规则（优先级从高到低）：
        1. 硬冲突 → PAUSED
        2. 预算超限 → DEGRADED
        3. 高风险 + 低置信度 → PAUSED
        4. 多个 LLM fallback → DEGRADED
        5. 软冲突 → MINIMAL
        6. 其他 → NORMAL
        """
        # 检测冲突
        conflicts = self.conflict_detector.detect_conflicts(reports)
        hard_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.HARD]
        soft_conflicts = [c for c in conflicts if c.severity == ConflictSeverity.SOFT]
        
        # 计算指标
        metrics = self._calculate_metrics(reports, total_cost, budget_limit, llm_fallback_count)
        
        # 规则 1: 硬冲突 → PAUSED
        if hard_conflicts:
            return GovernanceDecision(
                execution_mode=ExecutionMode.PAUSED,
                restrictions=["Execution paused due to hard conflicts"],
                reasoning=f"Hard conflicts detected: {', '.join([c.conflict_type for c in hard_conflicts])}. System requires human review.",
                conflicts=conflicts,
                metrics=metrics
            )
        
        # 规则 2: 预算超限 → DEGRADED
        budget_remaining = budget_limit - total_cost
        if budget_remaining < 0:
            return GovernanceDecision(
                execution_mode=ExecutionMode.DEGRADED,
                restrictions=["Budget exceeded, using minimal features only"],
                reasoning=f"Budget limit ({budget_limit}) exceeded. Current cost: {total_cost}. Switching to degraded mode.",
                conflicts=conflicts,
                metrics=metrics
            )
        
        # 规则 3: 高风险 + 低置信度 → PAUSED
        high_risk_reports = [r for r in reports if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        low_confidence_reports = [r for r in reports if r.confidence < 0.5]
        if len(high_risk_reports) >= 2 and len(low_confidence_reports) >= 2:
            return GovernanceDecision(
                execution_mode=ExecutionMode.PAUSED,
                restrictions=["High risk and low confidence detected"],
                reasoning=f"Multiple high-risk agents ({len(high_risk_reports)}) with low confidence ({len(low_confidence_reports)}). System requires human review.",
                conflicts=conflicts,
                metrics=metrics
            )
        
        # 规则 4: 多个 LLM fallback → DEGRADED
        if llm_fallback_count >= 3:
            return GovernanceDecision(
                execution_mode=ExecutionMode.DEGRADED,
                restrictions=["Multiple LLM fallbacks, using deterministic logic only"],
                reasoning=f"LLM fallback count ({llm_fallback_count}) exceeds threshold. Switching to degraded mode with deterministic logic.",
                conflicts=conflicts,
                metrics=metrics
            )
        
        # 规则 5: 软冲突 → MINIMAL
        if soft_conflicts:
            return GovernanceDecision(
                execution_mode=ExecutionMode.MINIMAL,
                restrictions=["Soft conflicts detected, using minimal execution"],
                reasoning=f"Soft conflicts detected: {', '.join([c.conflict_type for c in soft_conflicts])}. Using minimal execution mode.",
                conflicts=conflicts,
                metrics=metrics
            )
        
        # 规则 6: 正常执行
        return GovernanceDecision(
            execution_mode=ExecutionMode.NORMAL,
            restrictions=[],
            reasoning="All checks passed. Proceeding with normal execution.",
            conflicts=conflicts,
            metrics=metrics
        )
    
    def _calculate_metrics(
        self,
        reports: List[AgentExecutionReport],
        total_cost: float,
        budget_limit: float,
        llm_fallback_count: int
    ) -> Dict[str, Any]:
        """计算系统指标"""
        avg_confidence = sum(r.confidence for r in reports) / len(reports) if reports else 0.0
        high_risk_count = sum(1 for r in reports if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL])
        total_cost_impact = sum(r.cost_impact for r in reports)
        budget_utilization = (total_cost / budget_limit * 100) if budget_limit > 0 else 0.0
        
        return {
            "avg_confidence": avg_confidence,
            "high_risk_count": high_risk_count,
            "total_cost": total_cost,
            "total_cost_impact": total_cost_impact,
            "budget_limit": budget_limit,
            "budget_remaining": budget_limit - total_cost,
            "budget_utilization_percent": budget_utilization,
            "llm_fallback_count": llm_fallback_count,
            "llm_fallback_rate": llm_fallback_count / len(reports) if reports else 0.0
        }

