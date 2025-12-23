"""
Policy KPI Collector: 策略级 KPI 收集器
收集线上监控窗口内各 policy 的性能指标
"""
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta


class PolicyKPICollector:
    """
    Policy KPI Collector：按 policy_id 聚合 KPI 指标。
    
    指标包括：
    - success_rate: 成功率
    - avg_cost: 平均成本
    - p95_latency: P95 延迟
    - failure_rate: 失败率
    - total_runs: 总运行数
    """
    
    def __init__(self, trace_store):
        """
        初始化 KPI Collector。
        
        Args:
            trace_store: TraceStore 实例
        """
        self.trace_store = trace_store
    
    def collect(
        self,
        lookback_minutes: int = 60,
        min_runs: int = 200
    ) -> Dict[str, Dict[str, Any]]:
        """
        按 policy_id 聚合 KPI 指标。
        
        Args:
            lookback_minutes: 回看时间窗口（分钟）
            min_runs: 最小 run 数（如果数据不足，会尝试扩大窗口）
            
        Returns:
            dict: {policy_id: {success_rate, avg_cost, p95_latency, failure_rate, total_runs}}
        """
        # 获取时间窗口
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=lookback_minutes)
        
        # 从 TraceStore 获取所有任务
        all_task_ids = self._get_all_task_ids()
        
        if not all_task_ids:
            return {}
        
        # 按 policy_id 分组收集数据
        policy_runs: Dict[str, List[Dict[str, Any]]] = {}
        
        for task_id in all_task_ids:
            summary = self.trace_store.load_summary(task_id)
            if not summary:
                continue
            
            # 检查时间窗口
            created_at = summary.created_at
            if created_at:
                try:
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    # 移除时区信息以便比较
                    created_time = created_time.replace(tzinfo=None)
                    if created_time < cutoff_time:
                        continue
                except (ValueError, AttributeError):
                    pass  # 如果时间解析失败，包含该任务
            
            # 确定 policy_id
            policy_id = summary.current_plan_id or "unknown"
            # 简化 policy_id（从 plan_id 提取版本）
            if "_" in policy_id:
                # 例如 "normal_v1" -> "v1"
                parts = policy_id.split("_")
                if len(parts) >= 2 and parts[-1].startswith("v"):
                    policy_id = parts[-1]
            
            # 提取 run 数据
            run_data = {
                "task_id": task_id,
                "state": summary.state,
                "is_success": summary.state in ["COMPLETED", "SUCCESS"],
                "cost": summary.cost_summary.get("total", 0.0) if summary.cost_summary else 0.0,
                "created_at": created_at
            }
            
            # 从 events 计算 step_count（用于近似 latency）
            events, _ = self.trace_store.load_events(task_id, limit=100)
            step_count = len([e for e in events if e.type == "agent_report"])
            run_data["latency"] = step_count * 200  # 近似 latency（每步 200ms）
            
            if policy_id not in policy_runs:
                policy_runs[policy_id] = []
            policy_runs[policy_id].append(run_data)
        
        # 如果数据不足，尝试包含更多（但不扩大窗口，只是不过滤时间）
        total_runs = sum(len(runs) for runs in policy_runs.values())
        if total_runs < min_runs:
            # 重新收集，不过滤时间
            policy_runs = self._collect_all_without_time_filter(all_task_ids)
        
        # 计算各 policy 的 KPI
        result = {}
        for policy_id, runs in policy_runs.items():
            result[policy_id] = self._calculate_kpis(runs)
        
        return result
    
    def _get_all_task_ids(self) -> List[str]:
        """获取所有任务 ID"""
        all_task_ids = self.trace_store.query_tasks({})
        
        # 如果索引为空，从 summaries 目录读取
        if not all_task_ids:
            summaries_dir = self.trace_store.summaries_dir
            if os.path.exists(summaries_dir):
                all_task_ids = [
                    f[:-5] for f in os.listdir(summaries_dir)
                    if f.endswith('.json')
                ]
        
        return all_task_ids
    
    def _collect_all_without_time_filter(
        self,
        all_task_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """收集所有数据（不过滤时间）"""
        policy_runs: Dict[str, List[Dict[str, Any]]] = {}
        
        for task_id in all_task_ids:
            summary = self.trace_store.load_summary(task_id)
            if not summary:
                continue
            
            policy_id = summary.current_plan_id or "unknown"
            if "_" in policy_id:
                parts = policy_id.split("_")
                if len(parts) >= 2 and parts[-1].startswith("v"):
                    policy_id = parts[-1]
            
            run_data = {
                "task_id": task_id,
                "state": summary.state,
                "is_success": summary.state in ["COMPLETED", "SUCCESS"],
                "cost": summary.cost_summary.get("total", 0.0) if summary.cost_summary else 0.0,
                "created_at": summary.created_at
            }
            
            events, _ = self.trace_store.load_events(task_id, limit=100)
            step_count = len([e for e in events if e.type == "agent_report"])
            run_data["latency"] = step_count * 200
            
            if policy_id not in policy_runs:
                policy_runs[policy_id] = []
            policy_runs[policy_id].append(run_data)
        
        return policy_runs
    
    def _calculate_kpis(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算单个 policy 的 KPI"""
        if not runs:
            return {
                "success_rate": 0.0,
                "avg_cost": 0.0,
                "p95_latency": 0.0,
                "failure_rate": 0.0,
                "total_runs": 0
            }
        
        total = len(runs)
        success_count = sum(1 for r in runs if r.get("is_success"))
        failed_count = total - success_count
        
        # Success rate
        success_rate = success_count / total if total > 0 else 0.0
        
        # Failure rate
        failure_rate = failed_count / total if total > 0 else 0.0
        
        # Average cost
        costs = [r.get("cost", 0.0) for r in runs]
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        
        # P95 latency
        latencies = sorted([r.get("latency", 0) for r in runs])
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_idx] if p95_idx < len(latencies) else (latencies[-1] if latencies else 0)
        
        return {
            "success_rate": round(success_rate, 4),
            "avg_cost": round(avg_cost, 4),
            "p95_latency": round(p95_latency, 2),
            "failure_rate": round(failure_rate, 4),
            "total_runs": total
        }



