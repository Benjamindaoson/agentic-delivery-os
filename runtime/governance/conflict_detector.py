"""
Conflict Detector: 检测 Agent 之间的分歧
"""
from typing import List, Dict, Any
from enum import Enum
from runtime.governance.agent_report import AgentExecutionReport

class ConflictSeverity(str, Enum):
    """冲突严重性"""
    SOFT = "soft"  # 可容忍的不一致
    HARD = "hard"  # 必须处理的不一致

class Conflict:
    """冲突记录"""
    def __init__(
        self,
        conflict_type: str,
        agents_involved: List[str],
        evidence: Dict[str, Any],
        severity: ConflictSeverity,
        suggested_action: str
    ):
        self.conflict_type = conflict_type
        self.agents_involved = agents_involved
        self.evidence = evidence
        self.severity = severity
        self.suggested_action = suggested_action
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_type": self.conflict_type,
            "agents_involved": self.agents_involved,
            "evidence": self.evidence,
            "severity": self.severity.value,
            "suggested_action": self.suggested_action
        }

class ConflictDetector:
    """冲突检测器"""
    
    def __init__(self):
        pass
    
    def detect_conflicts(self, reports: List[AgentExecutionReport]) -> List[Conflict]:
        """检测 Agent 报告之间的冲突"""
        conflicts = []
        
        # 1. 检测决策冲突
        decisions = {}
        for report in reports:
            if report.agent_name in ["Product", "Evaluation", "Cost"]:
                decisions[report.agent_name] = report.decision
        
        # Product vs Evaluation: 如果 Product 通过但 Evaluation 不通过
        if "Product" in decisions and "Evaluation" in decisions:
            if decisions["Product"] == "proceed" and decisions["Evaluation"] != "passed":
                conflicts.append(Conflict(
                    conflict_type="decision_mismatch",
                    agents_involved=["Product", "Evaluation"],
                    evidence={
                        "product_decision": decisions["Product"],
                        "evaluation_decision": decisions["Evaluation"]
                    },
                    severity=ConflictSeverity.HARD,
                    suggested_action="Review evaluation criteria or product spec"
                ))
        
        # 2. 检测置信度冲突
        low_confidence_agents = [
            r.agent_name for r in reports 
            if r.confidence < 0.5 and r.agent_name in ["Product", "Evaluation"]
        ]
        if len(low_confidence_agents) >= 2:
            conflicts.append(Conflict(
                conflict_type="low_confidence_cluster",
                agents_involved=low_confidence_agents,
                evidence={
                    "agents": low_confidence_agents,
                    "confidence_threshold": 0.5
                },
                severity=ConflictSeverity.SOFT,
                suggested_action="Consider manual review or spec clarification"
            ))
        
        # 3. 检测风险级别冲突
        high_risk_agents = [
            r.agent_name for r in reports 
            if r.risk_level.value in ["high", "critical"]
        ]
        if high_risk_agents:
            conflicts.append(Conflict(
                conflict_type="risk_escalation",
                agents_involved=high_risk_agents,
                evidence={
                    "high_risk_agents": high_risk_agents
                },
                severity=ConflictSeverity.HARD if len(high_risk_agents) >= 2 else ConflictSeverity.SOFT,
                suggested_action="Pause execution and request human review"
            ))
        
        # 4. 检测成本信号冲突
        cost_reports = [r for r in reports if r.agent_name == "Cost"]
        if cost_reports:
            cost_report = cost_reports[0]
            if cost_report.decision == "continue" and cost_report.signals.get("budget_remaining", 1000) < 100:
                conflicts.append(Conflict(
                    conflict_type="budget_warning",
                    agents_involved=["Cost"],
                    evidence={
                        "budget_remaining": cost_report.signals.get("budget_remaining"),
                        "decision": cost_report.decision
                    },
                    severity=ConflictSeverity.SOFT,
                    suggested_action="Consider budget constraints in next phase"
                ))
        
        return conflicts

