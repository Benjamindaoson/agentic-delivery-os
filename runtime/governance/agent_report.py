"""
Agent Execution Report: 统一的 Agent 执行报告结构
将 Agent 输出信号化，供系统治理层使用
"""
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

class AgentStatus(str, Enum):
    """Agent 执行状态"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"

class RiskLevel(str, Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AgentExecutionReport:
    """Agent 执行报告：结构化的系统信号"""
    
    def __init__(
        self,
        agent_name: str,
        decision: str,
        status: AgentStatus,
        confidence: float = 1.0,
        risk_level: RiskLevel = RiskLevel.LOW,
        cost_impact: float = 0.0,
        signals: Optional[Dict[str, Any]] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None,
        llm_fallback_used: bool = False
    ):
        self.agent_name = agent_name
        self.decision = decision
        self.status = status
        self.confidence = confidence  # 0.0 - 1.0
        self.risk_level = risk_level
        self.cost_impact = cost_impact
        self.signals = signals or {}  # 结构化信号
        self.conflicts = conflicts or []  # 与其他 Agent 的冲突
        self.llm_fallback_used = llm_fallback_used
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 trace 记录"""
        return {
            "agent_name": self.agent_name,
            "decision": self.decision,
            "status": self.status.value,
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "cost_impact": self.cost_impact,
            "signals": self.signals,
            "conflicts": self.conflicts,
            "llm_fallback_used": self.llm_fallback_used,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_agent_result(cls, agent_name: str, result: Dict[str, Any]) -> "AgentExecutionReport":
        """从 Agent 执行结果创建报告"""
        decision = result.get("decision", "unknown")
        status = AgentStatus.SUCCESS
        
        # 提取信号
        signals = {}
        confidence = 1.0
        risk_level = RiskLevel.LOW
        cost_impact = 0.0
        conflicts = []
        llm_fallback_used = False
        
        # 从 result 中提取信息
        if "llm_result" in result:
            llm_result = result.get("llm_result", {})
            llm_fallback_used = llm_result.get("fallback_used", False)
            if llm_result.get("llm_used"):
                # LLM 成功使用
                signals["llm_used"] = True
                signals["llm_provider"] = llm_result.get("provider")
                if "output_summary" in llm_result:
                    output_summary = llm_result["output_summary"]
                    if "confidence_level" in output_summary:
                        conf_level = output_summary["confidence_level"]
                        if conf_level == "low":
                            confidence = 0.3
                            risk_level = RiskLevel.MEDIUM
                        elif conf_level == "medium":
                            confidence = 0.6
                            risk_level = RiskLevel.LOW
                        elif conf_level == "high":
                            confidence = 0.9
            else:
                # LLM fallback
                signals["llm_fallback"] = True
                signals["llm_failure_code"] = llm_result.get("failure_code")
                confidence = 0.5  # LLM fallback 降低置信度
        
        # 从 state_update 中提取信号
        state_update = result.get("state_update", {})
        if "cost_usage" in state_update:
            cost_impact = state_update.get("cost_usage", 0.0)
        if "budget_remaining" in state_update:
            signals["budget_remaining"] = state_update.get("budget_remaining", 1000.0)
        
        # 评估状态
        if decision in ["terminate", "failed", "rejected"]:
            status = AgentStatus.ERROR
            risk_level = RiskLevel.HIGH
        elif decision in ["warning", "degraded"]:
            status = AgentStatus.WARNING
            risk_level = RiskLevel.MEDIUM
        
        return cls(
            agent_name=agent_name,
            decision=decision,
            status=status,
            confidence=confidence,
            risk_level=risk_level,
            cost_impact=cost_impact,
            signals=signals,
            conflicts=conflicts,
            llm_fallback_used=llm_fallback_used
        )
























