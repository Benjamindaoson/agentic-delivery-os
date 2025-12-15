"""
TraceStore: 分层存储 + 增量加载 + 索引
目标：解决 trace 体量膨胀导致的后端/前端性能风险
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class TraceSummary:
    """Trace 摘要：小体积、默认加载"""
    task_id: str
    state: str
    current_plan_id: Optional[str] = None
    current_plan_path_type: Optional[str] = None
    key_decisions_topk: List[Dict[str, Any]] = None  # Top-K 关键决策点
    cost_summary: Dict[str, float] = None  # 成本摘要
    result_summary: Dict[str, Any] = None  # 结果摘要
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        if self.key_decisions_topk is None:
            self.key_decisions_topk = []
        if self.cost_summary is None:
            self.cost_summary = {}
        if self.result_summary is None:
            self.result_summary = {}

@dataclass
class TraceEvent:
    """Trace 事件：事件流（append-only）"""
    event_id: str  # 单调递增或可排序
    task_id: str
    ts: str
    type: str  # agent_report/governance_decision/plan_switch/tool_call/state_change/evaluation_feedback/cost_update
    payload_ref: Optional[str] = None  # 指向 trace_store 的引用
    payload: Optional[Dict[str, Any]] = None  # 小 payload 可直接嵌入

@dataclass
class TraceBlob:
    """Trace 大对象：DAG 细节、工具输出、artifact引用"""
    blob_id: str
    task_id: str
    blob_type: str  # dag_detail/tool_output/artifact_ref
    content: Dict[str, Any]
    created_at: str

class TraceStore:
    """Trace 分层存储"""
    
    def __init__(self, base_dir: str = "artifacts/trace_store"):
        self.base_dir = base_dir
        self.summaries_dir = os.path.join(base_dir, "summaries")
        self.events_dir = os.path.join(base_dir, "events")
        self.blobs_dir = os.path.join(base_dir, "blobs")
        self.index_dir = os.path.join(base_dir, "index")
        
        # 创建目录
        for dir_path in [self.summaries_dir, self.events_dir, self.blobs_dir, self.index_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def save_summary(self, summary: TraceSummary) -> str:
        """保存 trace 摘要"""
        summary_path = os.path.join(self.summaries_dir, f"{summary.task_id}.json")
        summary.updated_at = datetime.now().isoformat()
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2, ensure_ascii=False)
        return summary_path
    
    def load_summary(self, task_id: str) -> Optional[TraceSummary]:
        """加载 trace 摘要"""
        summary_path = os.path.join(self.summaries_dir, f"{task_id}.json")
        if not os.path.exists(summary_path):
            return None
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return TraceSummary(**data)
    
    def save_event(self, event: TraceEvent) -> str:
        """保存事件（append-only）"""
        events_file = os.path.join(self.events_dir, f"{event.task_id}.jsonl")
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return events_file
    
    def load_events(self, task_id: str, cursor: Optional[str] = None, limit: int = 100) -> tuple[List[TraceEvent], Optional[str]]:
        """加载事件（分页/游标）"""
        events_file = os.path.join(self.events_dir, f"{task_id}.jsonl")
        if not os.path.exists(events_file):
            return [], None
        
        events = []
        with open(events_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        start_idx = 0
        if cursor:
            # 找到 cursor 位置
            for i, line in enumerate(lines):
                event_data = json.loads(line.strip())
                if event_data.get("event_id") == cursor:
                    start_idx = i + 1
                    break
        
        # 读取 limit 条
        for line in lines[start_idx:start_idx + limit]:
            event_data = json.loads(line.strip())
            events.append(TraceEvent(**event_data))
        
        # 计算下一个 cursor
        next_cursor = None
        if len(events) == limit and start_idx + limit < len(lines):
            next_cursor = events[-1].event_id
        
        return events, next_cursor
    
    def save_blob(self, blob: TraceBlob) -> str:
        """保存大对象"""
        blob_path = os.path.join(self.blobs_dir, f"{blob.task_id}_{blob.blob_id}.json")
        with open(blob_path, "w", encoding="utf-8") as f:
            json.dump(asdict(blob), f, indent=2, ensure_ascii=False)
        return blob_path
    
    def load_blob(self, task_id: str, blob_id: str) -> Optional[TraceBlob]:
        """加载大对象"""
        blob_path = os.path.join(self.blobs_dir, f"{task_id}_{blob_id}.json")
        if not os.path.exists(blob_path):
            return None
        with open(blob_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return TraceBlob(**data)
    
    def build_summary_from_trace(self, task_id: str, trace_data: Dict[str, Any]) -> TraceSummary:
        """从完整 trace 构建摘要"""
        # 提取关键决策点 Top-K（按显著性排序）
        key_decisions = []
        
        # 从 governance_decisions 提取
        gov_decisions = trace_data.get("governance_decisions", [])
        for decision in gov_decisions[-5:]:  # Top-5
            if decision.get("execution_mode") != "normal":
                key_decisions.append({
                    "type": "governance_decision",
                    "execution_mode": decision.get("execution_mode"),
                    "reasoning": decision.get("reasoning", "")[:200],
                    "timestamp": decision.get("timestamp")
                })
        
        # 从 plan_selection_history 提取
        plan_history = trace_data.get("execution_plan", {}).get("plan_selection_history", [])
        for selection in plan_history[-3:]:  # Top-3
            if selection.get("trigger"):
                key_decisions.append({
                    "type": "plan_selection",
                    "selected_plan_id": selection.get("selected_plan_id"),
                    "path_type": selection.get("path_type"),
                    "trigger": selection.get("trigger"),
                    "reasoning": selection.get("reasoning", "")[:200]
                })
        
        # 计算成本摘要
        agent_reports = trace_data.get("agent_reports", [])
        total_cost = sum(r.get("cost_impact", 0.0) for r in agent_reports)
        cost_by_agent = {}
        for report in agent_reports:
            agent_name = report.get("agent_name", "unknown")
            cost_by_agent[agent_name] = cost_by_agent.get(agent_name, 0.0) + report.get("cost_impact", 0.0)
        
        # 结果摘要
        state_transitions = trace_data.get("state_transitions", [])
        final_state = state_transitions[-1].get("state", "UNKNOWN") if state_transitions else "UNKNOWN"
        
        result_summary = {
            "final_state": final_state,
            "executed_agents_count": len(agent_reports),
            "has_degraded": any(
                d.get("execution_mode") in ["degraded", "minimal"]
                for d in gov_decisions
            ),
            "has_paused": any(
                d.get("execution_mode") == "paused"
                for d in gov_decisions
            )
        }
        
        return TraceSummary(
            task_id=task_id,
            state=final_state,
            current_plan_id=trace_data.get("execution_plan", {}).get("plan_id"),
            current_plan_path_type=trace_data.get("execution_plan", {}).get("path_type"),
            key_decisions_topk=key_decisions[:10],  # Top-10
            cost_summary={
                "total": total_cost,
                "by_agent": cost_by_agent
            },
            result_summary=result_summary,
            created_at=trace_data.get("generated_at"),
            updated_at=datetime.now().isoformat()
        )
    
    def index_trace(self, task_id: str, trace_data: Dict[str, Any]):
        """建立索引（按 task_id / ts / failure_type / mode / cost_range）"""
        index_file = os.path.join(self.index_dir, "tasks_index.jsonl")
        
        # 提取索引字段
        final_state = trace_data.get("state_transitions", [{}])[-1].get("state", "UNKNOWN")
        failure_type = trace_data.get("evaluation_feedback_flow", {}).get("last_failure_type")
        execution_mode = trace_data.get("governance_decisions", [{}])[-1].get("execution_mode", "normal")
        total_cost = sum(r.get("cost_impact", 0.0) for r in trace_data.get("agent_reports", []))
        
        index_entry = {
            "task_id": task_id,
            "ts": trace_data.get("generated_at", datetime.now().isoformat()),
            "state": final_state,
            "failure_type": failure_type,
            "execution_mode": execution_mode,
            "cost_range": self._get_cost_range(total_cost)
        }
        
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(index_entry, ensure_ascii=False) + "\n")
    
    def _get_cost_range(self, cost: float) -> str:
        """成本范围分类"""
        if cost < 10:
            return "low"
        elif cost < 100:
            return "medium"
        elif cost < 1000:
            return "high"
        else:
            return "very_high"
    
    def query_tasks(self, filter_params: Dict[str, Any]) -> List[str]:
        """查询任务（按时间范围、状态、failure_type）"""
        index_file = os.path.join(self.index_dir, "tasks_index.jsonl")
        if not os.path.exists(index_file):
            return []
        
        matching_tasks = []
        with open(index_file, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line.strip())
                
                # 应用过滤条件
                if "state" in filter_params and entry.get("state") != filter_params["state"]:
                    continue
                if "failure_type" in filter_params and entry.get("failure_type") != filter_params["failure_type"]:
                    continue
                if "execution_mode" in filter_params and entry.get("execution_mode") != filter_params["execution_mode"]:
                    continue
                if "cost_range" in filter_params and entry.get("cost_range") != filter_params["cost_range"]:
                    continue
                
                matching_tasks.append(entry["task_id"])
        
        return matching_tasks


