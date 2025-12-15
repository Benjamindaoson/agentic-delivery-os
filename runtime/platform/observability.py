"""
Observability: 可观测与SLO
目标：平台可运营，具备 SLO 指标与诊断能力
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

@dataclass
class SLOMetrics:
    """SLO 指标"""
    latency_p50: float  # 毫秒
    latency_p95: float
    cost_tokens: float
    cost_usd: float
    success_rate: float
    pause_rate: float
    degrade_rate: float
    manual_takeover_rate: float
    goal_done_rate: float
    goal_partial_rate: float
    goal_not_done_rate: float

@dataclass
class TraceGap:
    """Trace 间隙"""
    task_id: str
    gap_start: str
    gap_end: str
    gap_duration_seconds: float
    missing_event_types: List[str]

@dataclass
class SlowPath:
    """慢路径识别"""
    task_id: str
    stage: str
    duration_seconds: float
    threshold_seconds: float
    affected_nodes: List[str]

class ObservabilityEngine:
    """可观测引擎"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "slow_path_threshold_seconds": 30.0,
            "gap_detection_window_seconds": 60.0
        }
        self.version = "1.0"
    
    def calculate_slo_metrics(self, tasks: List[Dict[str, Any]]) -> SLOMetrics:
        """计算 SLO 指标（确定性规则）"""
        if not tasks:
            return SLOMetrics(
                latency_p50=0.0, latency_p95=0.0,
                cost_tokens=0.0, cost_usd=0.0,
                success_rate=0.0, pause_rate=0.0, degrade_rate=0.0,
                manual_takeover_rate=0.0,
                goal_done_rate=0.0, goal_partial_rate=0.0, goal_not_done_rate=0.0
            )
        
        latencies = []
        total_tokens = 0.0
        total_usd = 0.0
        success_count = 0
        pause_count = 0
        degrade_count = 0
        manual_takeover_count = 0
        goal_done_count = 0
        goal_partial_count = 0
        goal_not_done_count = 0
        
        for task in tasks:
            # 计算延迟
            created_at = task.get("created_at")
            completed_at = task.get("completed_at")
            if created_at and completed_at:
                delta = (datetime.fromisoformat(completed_at) - 
                        datetime.fromisoformat(created_at)).total_seconds() * 1000
                latencies.append(delta)
            
            # 累计成本
            cost_summary = task.get("cost_summary", {})
            total_tokens += cost_summary.get("total_tokens", 0.0)
            total_usd += cost_summary.get("total_usd", 0.0)
            
            # 状态统计
            state = task.get("state", "")
            if state == "COMPLETED":
                success_count += 1
            elif state == "PAUSED":
                pause_count += 1
            
            # 降级统计
            result_summary = task.get("result_summary", {})
            if result_summary.get("has_degraded"):
                degrade_count += 1
            
            # 目标完成度统计
            goal_status = task.get("goal_status", "")
            if goal_status == "DONE":
                goal_done_count += 1
            elif goal_status == "PARTIAL":
                goal_partial_count += 1
            elif goal_status == "NOT_DONE":
                goal_not_done_count += 1
        
        # 计算百分位数
        latencies.sort()
        n = len(latencies)
        latency_p50 = latencies[n // 2] if n > 0 else 0.0
        latency_p95 = latencies[int(n * 0.95)] if n > 0 else 0.0
        
        total_count = len(tasks)
        
        return SLOMetrics(
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            cost_tokens=total_tokens,
            cost_usd=total_usd,
            success_rate=success_count / total_count if total_count > 0 else 0.0,
            pause_rate=pause_count / total_count if total_count > 0 else 0.0,
            degrade_rate=degrade_count / total_count if total_count > 0 else 0.0,
            manual_takeover_rate=manual_takeover_count / total_count if total_count > 0 else 0.0,
            goal_done_rate=goal_done_count / total_count if total_count > 0 else 0.0,
            goal_partial_rate=goal_partial_count / total_count if total_count > 0 else 0.0,
            goal_not_done_rate=goal_not_done_count / total_count if total_count > 0 else 0.0
        )
    
    def detect_trace_gaps(self, task_id: str, events: List[Dict[str, Any]]) -> List[TraceGap]:
        """检测 trace 间隙（确定性规则）"""
        gaps = []
        if len(events) < 2:
            return gaps
        
        window_seconds = self.config["gap_detection_window_seconds"]
        
        for i in range(len(events) - 1):
            current_ts = datetime.fromisoformat(events[i]["ts"])
            next_ts = datetime.fromisoformat(events[i + 1]["ts"])
            gap_duration = (next_ts - current_ts).total_seconds()
            
            if gap_duration > window_seconds:
                gaps.append(TraceGap(
                    task_id=task_id,
                    gap_start=events[i]["ts"],
                    gap_end=events[i + 1]["ts"],
                    gap_duration_seconds=gap_duration,
                    missing_event_types=[]  # 可根据规则推断缺失事件类型
                ))
        
        return gaps
    
    def detect_slow_paths(self, task_id: str, trace_data: Dict[str, Any]) -> List[SlowPath]:
        """检测慢路径（确定性规则）"""
        slow_paths = []
        threshold = self.config["slow_path_threshold_seconds"]
        
        # 分析 Agent 执行时间
        agent_executions = trace_data.get("agent_executions", [])
        for exec_entry in agent_executions:
            timestamp = exec_entry.get("timestamp")
            if not timestamp:
                continue
            
            # 简化：假设每个 Agent 执行时间从开始到下一个事件
            # 实际应该从 trace 中提取更精确的时间信息
            # 这里用规则估算
            estimated_duration = 5.0  # 默认估算（实际应从 trace 提取）
            
            if estimated_duration > threshold:
                slow_paths.append(SlowPath(
                    task_id=task_id,
                    stage=exec_entry.get("agent", "unknown"),
                    duration_seconds=estimated_duration,
                    threshold_seconds=threshold,
                    affected_nodes=[exec_entry.get("agent", "unknown")]
                ))
        
        return slow_paths
    
    def generate_observability_report(self, task_ids: List[str]) -> Dict[str, Any]:
        """生成可观测性报告"""
        # 加载任务数据
        tasks = []
        for task_id in task_ids:
            from runtime.platform.trace_store import TraceStore
            trace_store = TraceStore()
            summary = trace_store.load_summary(task_id)
            if summary:
                tasks.append({
                    "task_id": summary.task_id,
                    "state": summary.state,
                    "created_at": summary.created_at,
                    "updated_at": summary.updated_at,
                    "cost_summary": summary.cost_summary,
                    "result_summary": summary.result_summary
                })
        
        # 计算指标
        metrics = self.calculate_slo_metrics(tasks)
        
        # 检测问题
        all_gaps = []
        all_slow_paths = []
        for task_id in task_ids:
            from runtime.platform.trace_store import TraceStore
            trace_store = TraceStore()
            events, _ = trace_store.load_events(task_id, limit=1000)
            event_dicts = [asdict(e) for e in events]
            gaps = self.detect_trace_gaps(task_id, event_dicts)
            all_gaps.extend(gaps)
            
            # 加载完整 trace 检测慢路径
            import os
            trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
            if os.path.exists(trace_path):
                with open(trace_path, "r", encoding="utf-8") as f:
                    trace_data = json.load(f)
                slow_paths = self.detect_slow_paths(task_id, trace_data)
                all_slow_paths.extend(slow_paths)
        
        return {
            "metrics": asdict(metrics),
            "trace_gaps": [asdict(g) for g in all_gaps],
            "slow_paths": [asdict(s) for s in all_slow_paths],
            "report_version": self.version,
            "generated_at": datetime.now().isoformat()
        }


