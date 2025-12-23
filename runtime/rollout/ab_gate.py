"""
A/B Gate: 策略发布门禁
基于 Shadow Eval 报告决定 candidate policy 是否可以进入灰度发布流程
"""
from typing import Dict, Any, List


class ABGate:
    """
    A/B Gate 门禁：决定 candidate policy 是否通过质量门禁。
    
    规则（AND，全部满足才通过）：
    1. candidate success_rate >= active success_rate + min_success_uplift
    2. candidate avg_cost <= active avg_cost * (1 + max_cost_increase)
    3. candidate p95_latency <= active p95_latency * (1 + max_latency_increase_p95)
    4. candidate evidence_pass_rate >= min_evidence_pass_rate
    """
    
    def __init__(
        self,
        min_success_uplift: float = 0.00,
        max_cost_increase: float = 0.05,
        max_latency_increase_p95: float = 0.10,
        min_evidence_pass_rate: float = 0.90
    ):
        """
        初始化 A/B Gate。
        
        Args:
            min_success_uplift: 最小成功率提升（默认 0%，不允许下降）
            max_cost_increase: 最大成本增加比例（默认 5%）
            max_latency_increase_p95: 最大 P95 延迟增加比例（默认 10%）
            min_evidence_pass_rate: 最小 evidence 通过率（默认 90%）
        """
        self.min_success_uplift = min_success_uplift
        self.max_cost_increase = max_cost_increase
        self.max_latency_increase_p95 = max_latency_increase_p95
        self.min_evidence_pass_rate = min_evidence_pass_rate
    
    def decide(self, shadow_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于 Shadow Eval 报告做出门禁决策。
        
        Args:
            shadow_report: ShadowEvaluator.evaluate() 的输出
            
        Returns:
            dict: {"gate_pass": bool, "reasons": [], "blocked_reasons": []}
        """
        metrics = shadow_report.get("metrics", {})
        
        # 提取指标
        success_rate_active = metrics.get("success_rate_active", 0.0)
        success_rate_candidate = metrics.get("success_rate_candidate", 0.0)
        avg_cost_active = metrics.get("avg_cost_active", 0.0)
        avg_cost_candidate = metrics.get("avg_cost_candidate", 0.0)
        p95_latency_active = metrics.get("p95_latency_active", 0.0)
        p95_latency_candidate = metrics.get("p95_latency_candidate", 0.0)
        evidence_pass_rate_active = metrics.get("evidence_pass_rate_active", 0.0)
        evidence_pass_rate_candidate = metrics.get("evidence_pass_rate_candidate", 0.0)
        
        reasons = []
        blocked_reasons = []
        
        # 规则 1: success_rate 检查
        success_uplift = success_rate_candidate - success_rate_active
        success_check = success_uplift >= self.min_success_uplift
        if success_check:
            if success_uplift > 0:
                reasons.append(f"success_rate +{success_uplift*100:.1f}%")
            else:
                reasons.append("success_rate maintained")
        else:
            blocked_reasons.append(
                f"success_rate dropped: {success_uplift*100:.1f}% < {self.min_success_uplift*100:.1f}%"
            )
        
        # 规则 2: avg_cost 检查
        if avg_cost_active > 0:
            cost_increase_ratio = (avg_cost_candidate - avg_cost_active) / avg_cost_active
        else:
            cost_increase_ratio = 0.0 if avg_cost_candidate == 0 else 1.0
        
        cost_check = cost_increase_ratio <= self.max_cost_increase
        if cost_check:
            if cost_increase_ratio < 0:
                reasons.append(f"cost {cost_increase_ratio*100:.1f}%")
            else:
                reasons.append("cost within limit")
        else:
            blocked_reasons.append(
                f"cost increase {cost_increase_ratio*100:.1f}% > {self.max_cost_increase*100:.1f}%"
            )
        
        # 规则 3: p95_latency 检查
        if p95_latency_active > 0:
            latency_increase_ratio = (p95_latency_candidate - p95_latency_active) / p95_latency_active
        else:
            latency_increase_ratio = 0.0 if p95_latency_candidate == 0 else 1.0
        
        latency_check = latency_increase_ratio <= self.max_latency_increase_p95
        if latency_check:
            if latency_increase_ratio < 0:
                reasons.append(f"p95_latency {latency_increase_ratio*100:.1f}%")
            else:
                reasons.append("latency within limit")
        else:
            blocked_reasons.append(
                f"p95_latency increase {latency_increase_ratio*100:.1f}% > {self.max_latency_increase_p95*100:.1f}%"
            )
        
        # 规则 4: evidence_pass_rate 检查
        evidence_check = evidence_pass_rate_candidate >= self.min_evidence_pass_rate
        if evidence_check:
            reasons.append(f"evidence_pass_rate {evidence_pass_rate_candidate*100:.1f}%")
        else:
            blocked_reasons.append(
                f"evidence_pass_rate {evidence_pass_rate_candidate*100:.1f}% < {self.min_evidence_pass_rate*100:.1f}%"
            )
        
        # 综合判断（AND 逻辑）
        gate_pass = success_check and cost_check and latency_check and evidence_check
        
        return {
            "gate_pass": gate_pass,
            "reasons": reasons,
            "blocked_reasons": blocked_reasons,
            "checks": {
                "success_rate": success_check,
                "avg_cost": cost_check,
                "p95_latency": latency_check,
                "evidence_pass_rate": evidence_check
            },
            "thresholds": {
                "min_success_uplift": self.min_success_uplift,
                "max_cost_increase": self.max_cost_increase,
                "max_latency_increase_p95": self.max_latency_increase_p95,
                "min_evidence_pass_rate": self.min_evidence_pass_rate
            }
        }



