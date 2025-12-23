"""
Tool Metrics: 工具可靠性追踪
维护 rolling stats 供 Learning 消费
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from runtime.tooling.tool_failure_classifier import ToolInvocationResult, ToolFailureType


@dataclass
class ToolStats:
    """单个工具的统计数据"""
    tool_name: str
    total_invocations: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    failure_type_distribution: Dict[str, int] = field(default_factory=dict)
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ToolMetricsCollector:
    """
    工具指标收集器：收集并持久化工具调用统计。
    
    每次工具调用后调用 record()，定期将 rolling stats 写入 artifacts/tool_stats.json。
    """
    
    def __init__(
        self,
        stats_path: str = "artifacts/tool_stats.json",
        max_history_per_tool: int = 1000
    ):
        """
        初始化工具指标收集器。
        
        Args:
            stats_path: 统计文件路径
            max_history_per_tool: 每个工具保留的最大历史记录数
        """
        self.stats_path = stats_path
        self.max_history_per_tool = max_history_per_tool
        self._stats: Dict[str, ToolStats] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # 加载现有统计
        self._load_stats()
    
    def record(self, result: ToolInvocationResult) -> None:
        """
        记录工具调用结果。
        
        Args:
            result: ToolInvocationResult
        """
        tool_name = result.tool_name
        
        # 初始化工具统计
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolStats(tool_name=tool_name)
        
        stats = self._stats[tool_name]
        
        # 更新计数
        stats.total_invocations += 1
        if result.success:
            stats.success_count += 1
        else:
            stats.failure_count += 1
            # 更新失败类型分布
            failure_type = result.failure_type.value if result.failure_type else "UNKNOWN"
            stats.failure_type_distribution[failure_type] = \
                stats.failure_type_distribution.get(failure_type, 0) + 1
        
        # 更新延迟
        stats.total_latency_ms += result.latency_ms
        stats.avg_latency_ms = stats.total_latency_ms / stats.total_invocations
        
        # 更新成本
        stats.total_cost += result.cost_estimate
        
        # 更新成功率
        stats.success_rate = stats.success_count / stats.total_invocations
        
        # 更新时间戳
        stats.last_updated = datetime.now().isoformat()
        
        # 添加到历史记录（用于 rolling window 分析）
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "success": result.success,
            "failure_type": result.failure_type.value if result.failure_type else None,
            "latency_ms": result.latency_ms,
            "cost_estimate": result.cost_estimate
        }
        self._history[tool_name].append(history_entry)
        
        # 限制历史记录大小
        if len(self._history[tool_name]) > self.max_history_per_tool:
            self._history[tool_name] = self._history[tool_name][-self.max_history_per_tool:]
        
        # 持久化
        self._save_stats()
    
    def get_tool_stats(self, tool_name: str) -> Optional[ToolStats]:
        """获取单个工具的统计"""
        return self._stats.get(tool_name)
    
    def get_all_stats(self) -> Dict[str, ToolStats]:
        """获取所有工具的统计"""
        return self._stats.copy()
    
    def get_rolling_stats(
        self,
        tool_name: str,
        window_size: int = 100
    ) -> Dict[str, Any]:
        """
        获取最近 N 次调用的滚动统计。
        
        Args:
            tool_name: 工具名称
            window_size: 窗口大小
            
        Returns:
            dict: rolling stats
        """
        history = self._history.get(tool_name, [])
        recent = history[-window_size:] if len(history) > window_size else history
        
        if not recent:
            return {
                "tool_name": tool_name,
                "window_size": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "failure_type_distribution": {}
            }
        
        success_count = sum(1 for r in recent if r["success"])
        total = len(recent)
        avg_latency = sum(r["latency_ms"] for r in recent) / total
        
        failure_dist: Dict[str, int] = defaultdict(int)
        for r in recent:
            if not r["success"] and r["failure_type"]:
                failure_dist[r["failure_type"]] += 1
        
        return {
            "tool_name": tool_name,
            "window_size": total,
            "success_rate": success_count / total,
            "avg_latency_ms": avg_latency,
            "failure_type_distribution": dict(failure_dist)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取所有工具的汇总统计（供 Learning 消费）。
        """
        tools = {}
        for tool_name, stats in self._stats.items():
            tools[tool_name] = {
                "success_rate": stats.success_rate,
                "avg_latency_ms": stats.avg_latency_ms,
                "total_invocations": stats.total_invocations,
                "failure_type_distribution": stats.failure_type_distribution
            }
        
        return {
            "tools": tools,
            "generated_at": datetime.now().isoformat()
        }
    
    def _load_stats(self) -> None:
        """从文件加载统计"""
        if not os.path.exists(self.stats_path):
            return
        
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for tool_name, stats_data in data.get("tools", {}).items():
                self._stats[tool_name] = ToolStats(
                    tool_name=tool_name,
                    total_invocations=stats_data.get("total_invocations", 0),
                    success_count=stats_data.get("success_count", 0),
                    failure_count=stats_data.get("failure_count", 0),
                    success_rate=stats_data.get("success_rate", 0.0),
                    avg_latency_ms=stats_data.get("avg_latency_ms", 0.0),
                    total_latency_ms=stats_data.get("total_latency_ms", 0.0),
                    total_cost=stats_data.get("total_cost", 0.0),
                    failure_type_distribution=stats_data.get("failure_type_distribution", {}),
                    last_updated=stats_data.get("last_updated", "")
                )
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save_stats(self) -> None:
        """保存统计到文件"""
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        
        data = {
            "tools": {
                name: stats.to_dict()
                for name, stats in self._stats.items()
            },
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例（供 ExecutionEngine 使用）
_tool_metrics_collector: Optional[ToolMetricsCollector] = None


def get_tool_metrics_collector() -> ToolMetricsCollector:
    """获取全局工具指标收集器"""
    global _tool_metrics_collector
    if _tool_metrics_collector is None:
        _tool_metrics_collector = ToolMetricsCollector()
    return _tool_metrics_collector



