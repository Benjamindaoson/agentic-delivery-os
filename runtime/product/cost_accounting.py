"""
Cost Accounting: 成本预测与计量闭环
执行前预测 + 执行后核算 + 偏差证据解释
确定性、可审计
"""
import hashlib
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from runtime.optimization.cost_forecaster import CostForecaster, CostForecast

@dataclass
class CostPrediction:
    """执行前预测"""
    predicted_tokens: int
    predicted_usd: float
    prediction_version: str
    prediction_hash: str

@dataclass
class CostAccounting:
    """执行后核算"""
    actual_tokens: int
    actual_usd: float
    delta_tokens: int
    delta_usd: float
    evidence_events: List[str]
    accounting_version: str
    accounting_hash: str

@dataclass
class CostDeltaExplanation:
    """成本偏差解释"""
    delta_type: str  # "over" or "under"
    delta_amount: float
    explanation_items: List[Dict[str, Any]]
    explanation_version: str

class CostAccountingEngine:
    """成本核算引擎（确定性、可审计）"""
    
    def __init__(self):
        self.forecaster = CostForecaster()
        self.version = "1.0"
    
    def predict(
        self,
        spec_length: int,
        node_count: int,
        tool_call_count: int,
        retry_count: int,
        path_type
    ) -> CostPrediction:
        """执行前预测"""
        forecast = self.forecaster.forecast(
            spec_length, node_count, tool_call_count, retry_count, path_type
        )
        
        # 使用预测区间的中点
        predicted_tokens = (forecast.predicted_tokens_min + forecast.predicted_tokens_max) // 2
        predicted_usd = (forecast.predicted_usd_min + forecast.predicted_usd_max) / 2
        
        # 计算 hash
        prediction_data = {
            "predicted_tokens": predicted_tokens,
            "predicted_usd": predicted_usd,
            "forecast_evidence": forecast.forecast_evidence
        }
        prediction_json = json.dumps(prediction_data, sort_keys=True)
        prediction_hash = hashlib.sha256(prediction_json.encode()).hexdigest()
        
        return CostPrediction(
            predicted_tokens=predicted_tokens,
            predicted_usd=predicted_usd,
            prediction_version=self.version,
            prediction_hash=prediction_hash
        )
    
    def account(
        self,
        trace_data: Dict[str, Any],
        prediction: CostPrediction
    ) -> CostAccounting:
        """执行后核算"""
        # 从 trace 提取实际成本
        agent_reports = trace_data.get("agent_reports", [])
        actual_tokens = sum(
            r.get("signals", {}).get("tokens_used", 0)
            for r in agent_reports
        )
        
        # 计算实际 USD（简化：基于 tokens）
        actual_usd = (actual_tokens / 1000) * 0.002  # $0.002 per 1k tokens
        
        # 计算偏差
        delta_tokens = actual_tokens - prediction.predicted_tokens
        delta_usd = actual_usd - prediction.predicted_usd
        
        # 提取证据事件（成本相关）
        evidence_events = []
        for i, report in enumerate(agent_reports):
            if report.get("cost_impact", 0) > 0:
                evidence_events.append(f"agent_report_{i}")
        
        # 计算 hash
        accounting_data = {
            "actual_tokens": actual_tokens,
            "actual_usd": actual_usd,
            "delta_tokens": delta_tokens,
            "delta_usd": delta_usd,
            "evidence_events": evidence_events
        }
        accounting_json = json.dumps(accounting_data, sort_keys=True)
        accounting_hash = hashlib.sha256(accounting_json.encode()).hexdigest()
        
        return CostAccounting(
            actual_tokens=actual_tokens,
            actual_usd=actual_usd,
            delta_tokens=delta_tokens,
            delta_usd=delta_usd,
            evidence_events=evidence_events,
            accounting_version=self.version,
            accounting_hash=accounting_hash
        )
    
    def explain_delta(
        self,
        accounting: CostAccounting,
        trace_data: Dict[str, Any]
    ) -> CostDeltaExplanation:
        """解释成本偏差（确定性规则）"""
        delta_type = "over" if accounting.delta_usd > 0 else "under"
        delta_amount = abs(accounting.delta_usd)
        
        explanation_items = []
        
        # 规则1：检查是否有额外重试
        agent_reports = trace_data.get("agent_reports", [])
        retry_count = sum(
            1 for r in agent_reports
            if r.get("llm_fallback_used", False)
        )
        if retry_count > 0:
            explanation_items.append({
                "reason": "LLM fallback retries",
                "count": retry_count,
                "impact": "increased_cost"
            })
        
        # 规则2：检查是否有降级（可能降低成本）
        governance_decisions = trace_data.get("governance_decisions", [])
        has_degraded = any(
            d.get("execution_mode") in ["degraded", "minimal"]
            for d in governance_decisions
        )
        if has_degraded and delta_type == "under":
            explanation_items.append({
                "reason": "Execution degraded",
                "impact": "reduced_cost"
            })
        
        # 规则3：检查工具调用数
        tool_executions = trace_data.get("tool_executions", [])
        tool_count = len(tool_executions)
        if tool_count > 0:
            explanation_items.append({
                "reason": "Tool executions",
                "count": tool_count,
                "impact": "increased_cost" if delta_type == "over" else "reduced_cost"
            })
        
        return CostDeltaExplanation(
            delta_type=delta_type,
            delta_amount=delta_amount,
            explanation_items=explanation_items,
            explanation_version=self.version
        )


