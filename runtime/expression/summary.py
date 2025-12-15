"""
Hierarchical Summary Engine: 分层摘要
必须分层（用户层 / 执行层 / 索引层）
每一句摘要都必须能定位证据
输出必须可 hash
"""
import hashlib
import json
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

@dataclass
class SummaryItem:
    """摘要项（每句绑定证据）"""
    text: str
    evidence: Dict[str, Any]  # event_id, trace_offset

@dataclass
class SummaryOutput:
    """摘要输出"""
    level_0: List[SummaryItem]  # 用户层
    level_1: List[SummaryItem]  # 执行层
    level_2: List[SummaryItem]  # 索引层
    summary_version: str
    summary_hash: str

class HierarchicalSummaryEngine:
    """分层摘要引擎（确定性规则）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "level_0_max_items": 3,
            "level_1_max_items": 10,
            "level_2_max_items": 50
        }
        self.version = "1.0"
    
    def summarize(self, trace_data: Dict[str, Any]) -> SummaryOutput:
        """
        生成分层摘要（确定性规则）
        
        规则：每句摘要必须绑定证据
        """
        level_0 = []
        level_1 = []
        level_2 = []
        
        # Level 0: 用户层（Top-3 关键决策）
        governance_decisions = trace_data.get("governance_decisions", [])
        for i, decision in enumerate(governance_decisions[-3:]):
            execution_mode = decision.get("execution_mode", "normal")
            reasoning = decision.get("reasoning", "")[:100]
            
            if execution_mode != "normal":
                text = f"系统因{reasoning}进入{execution_mode.upper()}模式"
                level_0.append(SummaryItem(
                    text=text,
                    evidence={
                        "event_id": f"gov_{len(governance_decisions) - 3 + i}",
                        "trace_offset": f"governance_decisions[{len(governance_decisions) - 3 + i}]",
                        "type": "governance_decision"
                    }
                ))
        
        # Level 1: 执行层（关键执行节点）
        agent_executions = trace_data.get("agent_executions", [])
        for i, exec_entry in enumerate(agent_executions[:10]):
            agent_name = exec_entry.get("agent", "unknown")
            decision = exec_entry.get("output", {}).get("decision", "unknown")
            
            level_1.append(SummaryItem(
                text=f"{agent_name} Agent 执行完成，决策：{decision}",
                evidence={
                    "event_id": exec_entry.get("agent"),
                    "trace_offset": f"agent_executions[{i}]",
                    "type": "agent_execution"
                }
            ))
        
        # Level 2: 索引层（所有事件摘要）
        plan_selection_history = trace_data.get("execution_plan", {}).get("plan_selection_history", [])
        for i, selection in enumerate(plan_selection_history[:50]):
            plan_id = selection.get("selected_plan_id", "unknown")
            path_type = selection.get("path_type", "unknown")
            
            level_2.append(SummaryItem(
                text=f"选择执行计划：{plan_id} ({path_type})",
                evidence={
                    "event_id": f"plan_selection_{i}",
                    "trace_offset": f"execution_plan.plan_selection_history[{i}]",
                    "type": "plan_selection"
                }
            ))
        
        # 计算 hash（确定性）
        summary_dict = {
            "level_0": [asdict(item) for item in level_0],
            "level_1": [asdict(item) for item in level_1],
            "level_2": [asdict(item) for item in level_2],
            "version": self.version
        }
        summary_json = json.dumps(summary_dict, sort_keys=True)
        summary_hash = hashlib.sha256(summary_json.encode()).hexdigest()
        
        return SummaryOutput(
            level_0=level_0,
            level_1=level_1,
            level_2=level_2,
            summary_version=self.version,
            summary_hash=summary_hash
        )


