"""
Deterministic Cost Forecaster: 可审计成本预测
输入特征（确定性）：spec长度、节点数、工具调用数、历史重试数、模式
输出区间：cost_forecast_tokens_range / latency_forecast_range
用途：仅用于用户提示/预算规划，不得作为裁决直接依据
"""
from typing import Dict, Any, Tuple
from dataclasses import dataclass
from runtime.execution_plan.plan_definition import PlanPath

@dataclass
class CostForecast:
    """成本预测"""
    predicted_tokens_min: int
    predicted_tokens_max: int
    predicted_usd_min: float
    predicted_usd_max: float
    predicted_latency_min: float  # 秒
    predicted_latency_max: float
    forecast_evidence: Dict[str, Any]

class CostForecaster:
    """成本预测器（确定性规则，非学习）"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "token_per_char": 0.25,  # 简化：每字符0.25 token
            "usd_per_1k_tokens": 0.002,  # 简化：每1k token $0.002
            "base_latency_per_node": 5.0,  # 秒
            "llm_call_overhead": 2.0  # 秒
        }
        self.version = "1.0"
    
    def forecast(
        self,
        spec_length: int,
        node_count: int,
        tool_call_count: int,
        retry_count: int,
        path_type: PlanPath
    ) -> CostForecast:
        """
        预测成本（确定性规则）
        
        Args:
            spec_length: spec 长度（字符数）
            node_count: 节点数
            tool_call_count: 工具调用数
            retry_count: 历史重试数
            path_type: 路径类型
        
        Returns:
            CostForecast: 成本预测
        """
        # 规则1：基础 token 估算
        base_tokens = int(spec_length * self.config["token_per_char"])
        
        # 规则2：每个节点估算 token（确定性）
        node_tokens = {
            PlanPath.NORMAL: 2000,
            PlanPath.DEGRADED: 1500,
            PlanPath.MINIMAL: 1000
        }.get(path_type, 1500)
        
        total_tokens_base = base_tokens + (node_count * node_tokens)
        
        # 规则3：重试增加成本（确定性）
        retry_multiplier = 1.0 + (retry_count * 0.1)
        total_tokens = int(total_tokens_base * retry_multiplier)
        
        # 规则4：工具调用增加成本（确定性）
        tool_tokens = tool_call_count * 100  # 每个工具调用100 token
        total_tokens += tool_tokens
        
        # 规则5：计算区间（±20%）
        tokens_min = int(total_tokens * 0.8)
        tokens_max = int(total_tokens * 1.2)
        
        # 规则6：转换为 USD
        usd_min = (tokens_min / 1000) * self.config["usd_per_1k_tokens"]
        usd_max = (tokens_max / 1000) * self.config["usd_per_1k_tokens"]
        
        # 规则7：延迟预测（确定性）
        base_latency = node_count * self.config["base_latency_per_node"]
        llm_overhead = node_count * self.config["llm_call_overhead"]
        total_latency_base = base_latency + llm_overhead
        
        # 重试增加延迟
        latency_with_retry = total_latency_base * retry_multiplier
        
        latency_min = latency_with_retry * 0.8
        latency_max = latency_with_retry * 1.2
        
        # 生成证据
        forecast_evidence = {
            "forecaster_version": self.version,
            "input_features": {
                "spec_length": spec_length,
                "node_count": node_count,
                "tool_call_count": tool_call_count,
                "retry_count": retry_count,
                "path_type": path_type.value
            },
            "calculation_steps": {
                "base_tokens": base_tokens,
                "node_tokens_per_node": node_tokens,
                "total_node_tokens": node_count * node_tokens,
                "retry_multiplier": retry_multiplier,
                "tool_tokens": tool_tokens,
                "total_tokens_base": total_tokens,
                "tokens_range": [tokens_min, tokens_max],
                "latency_base": total_latency_base,
                "latency_range": [latency_min, latency_max]
            }
        }
        
        return CostForecast(
            predicted_tokens_min=tokens_min,
            predicted_tokens_max=tokens_max,
            predicted_usd_min=usd_min,
            predicted_usd_max=usd_max,
            predicted_latency_min=latency_min,
            predicted_latency_max=latency_max,
            forecast_evidence=forecast_evidence
        )


