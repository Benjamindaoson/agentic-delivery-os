"""
Salience Engine: 显著性排序
只能基于确定规则
排序结果必须稳定
同输入必得同输出
"""
import hashlib
import json
from typing import Dict, Any, List
from dataclasses import dataclass, asdict

@dataclass
class SalienceInput:
    """Salience 输入"""
    task_id: str
    events: List[Dict[str, Any]]

@dataclass
class SalienceOutput:
    """Salience 输出"""
    ranked_event_ids: List[str]
    salience_version: str
    salience_hash: str

class SalienceEngine:
    """显著性排序引擎（确定性规则）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "severity_weights": {
                "governance": 3.0,
                "plan_switch": 2.5,
                "agent_report": 2.0,
                "cost_update": 1.5,
                "tool_call": 1.0,
                "state_change": 1.0
            },
            "governance_priority": {
                "paused": 10,
                "degraded": 8,
                "minimal": 6,
                "normal": 4
            }
        }
        self.version = "1.0"
    
    def rank(self, input_data: SalienceInput) -> SalienceOutput:
        """
        排序事件（确定性规则）
        
        规则：severity → governance_priority → time (desc)
        """
        events = input_data.events
        
        # 计算每个事件的显著性分数（确定性规则）
        scored_events = []
        for event in events:
            event_type = event.get("type", "unknown")
            severity = event.get("severity", 1)
            
            # 规则1：severity 权重
            type_weight = self.config["severity_weights"].get(event_type, 1.0)
            base_score = severity * type_weight
            
            # 规则2：governance 优先级
            if event_type == "governance_decision":
                execution_mode = event.get("payload", {}).get("execution_mode", "normal")
                gov_priority = self.config["governance_priority"].get(execution_mode, 4)
                base_score *= gov_priority
            
            # 规则3：时间（越新越重要，但权重较低）
            time_bonus = 0.1  # 简化：时间因素权重低
            
            total_score = base_score + time_bonus
            
            scored_events.append({
                "event_id": event.get("event_id"),
                "score": total_score,
                "event": event
            })
        
        # 排序：score 降序，然后 event_id（确保稳定）
        scored_events.sort(key=lambda x: (-x["score"], x["event_id"]))
        
        ranked_event_ids = [e["event_id"] for e in scored_events]
        
        # 计算 hash（确定性）
        input_json = json.dumps(asdict(input_data), sort_keys=True)
        output_json = json.dumps({"ranked_event_ids": ranked_event_ids}, sort_keys=True)
        combined = input_json + output_json + self.version
        salience_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        return SalienceOutput(
            ranked_event_ids=ranked_event_ids,
            salience_version=self.version,
            salience_hash=salience_hash
        )


