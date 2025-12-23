"""
Policy Trainer: 基于训练样本生成 policy artifact（规则型 v1）
不使用 ML/RL，使用统计规则、阈值更新、排序策略
"""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict, Counter


def train_policy_from_examples(
    examples: List[Dict[str, Any]],
    *,
    base_policy: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    从训练样本中生成新的 policy artifact。

    policy 至少包含：
    - policy_version
    - plan_selection_rules
    - thresholds（cost / failure / latency）
    - metadata（generated_at / source_runs_count）
    """
    if not examples:
        # 如果没有样本，返回基础策略或默认策略
        if base_policy:
            return base_policy.copy()
        return _default_policy()
    
    # 统计信息
    total_runs = len(examples)
    success_runs = [e for e in examples if e.get("outcome", {}).get("status") == "success"]
    failed_runs = [e for e in examples if e.get("outcome", {}).get("status") == "failed"]
    degraded_runs = [e for e in examples if e.get("outcome", {}).get("status") == "degraded"]
    
    success_rate = len(success_runs) / total_runs if total_runs > 0 else 0.0
    failure_rate = len(failed_runs) / total_runs if total_runs > 0 else 0.0
    
    # 1. Plan Selection Rules（基于成功率统计）
    plan_selection_rules = _learn_plan_selection_rules(examples, base_policy)
    
    # 2. Thresholds（基于成本、延迟、失败率统计）
    thresholds = _learn_thresholds(examples, base_policy)
    
    # 3. 生成版本号（基于 base_policy 或递增）
    if base_policy:
        base_version = base_policy.get("policy_version", "v1")
        # 简单递增版本号
        version_num = _extract_version_number(base_version)
        policy_version = f"v{version_num + 1}"
    else:
        policy_version = "v1"
    
    # 构建 policy artifact
    policy = {
        "policy_version": policy_version,
        "plan_selection_rules": plan_selection_rules,
        "thresholds": thresholds,
        "metadata": {
            "generated_at": datetime.now().timestamp(),
            "source_runs": total_runs,
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "statistics": {
                "total_runs": total_runs,
                "success_count": len(success_runs),
                "failed_count": len(failed_runs),
                "degraded_count": len(degraded_runs)
            }
        }
    }
    
    return policy


def _learn_plan_selection_rules(
    examples: List[Dict[str, Any]],
    base_policy: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """学习计划选择规则（基于成功率）"""
    
    # 统计每个 plan 的成功率
    plan_stats = defaultdict(lambda: {"success": 0, "total": 0, "avg_cost": 0.0, "avg_latency": 0.0})
    
    for example in examples:
        plan_id = example.get("selected_plan", {}).get("plan_id", "unknown")
        outcome = example.get("outcome", {})
        cost = example.get("cost", {})
        
        plan_stats[plan_id]["total"] += 1
        if outcome.get("status") == "success":
            plan_stats[plan_id]["success"] += 1
        
        # 累计成本（用于计算平均值）
        plan_stats[plan_id]["avg_cost"] += cost.get("usd", 0.0)
        plan_stats[plan_id]["avg_latency"] += cost.get("latency_ms", 0) or 0
    
    # 计算成功率和平均成本
    for plan_id, stats in plan_stats.items():
        if stats["total"] > 0:
            stats["success_rate"] = stats["success"] / stats["total"]
            stats["avg_cost"] = stats["avg_cost"] / stats["total"]
            stats["avg_latency"] = stats["avg_latency"] / stats["total"]
    
    # 选择最佳 plan（成功率最高，成本合理）
    prefer_plan = "normal"
    if plan_stats:
        # 优先选择成功率最高且样本数足够的 plan
        sorted_plans = sorted(
            plan_stats.items(),
            key=lambda x: (x[1].get("success_rate", 0.0), x[1].get("total", 0)),
            reverse=True
        )
        best_plan = sorted_plans[0][0]
        if plan_stats[best_plan]["total"] >= 3:  # 至少 3 个样本才信任
            prefer_plan = best_plan
    
    # 构建 fallback 顺序（基于成功率）
    fallback_order = ["normal", "degraded", "minimal"]
    if plan_stats:
        sorted_by_success = sorted(
            plan_stats.items(),
            key=lambda x: x[1].get("success_rate", 0.0),
            reverse=True
        )
        fallback_order = [p[0] for p in sorted_by_success if p[1].get("total", 0) > 0]
        # 确保至少包含默认顺序
        for default_plan in ["normal", "degraded", "minimal"]:
            if default_plan not in fallback_order:
                fallback_order.append(default_plan)
    
    # 如果有 base_policy，可以考虑继承其规则
    if base_policy and "plan_selection_rules" in base_policy:
        base_rules = base_policy["plan_selection_rules"]
        # 如果新数据不足，使用 base 规则
        total_samples = sum(s["total"] for s in plan_stats.values())
        if total_samples < 5:
            prefer_plan = base_rules.get("prefer_plan", prefer_plan)
            fallback_order = base_rules.get("fallback_order", fallback_order)
    
    return {
        "prefer_plan": prefer_plan,
        "fallback_order": fallback_order,
        "plan_statistics": {
            plan_id: {
                "success_rate": stats.get("success_rate", 0.0),
                "total_runs": stats.get("total", 0),
                "avg_cost_usd": stats.get("avg_cost", 0.0),
                "avg_latency_ms": stats.get("avg_latency", 0.0)
            }
            for plan_id, stats in plan_stats.items()
        }
    }


def _learn_thresholds(
    examples: List[Dict[str, Any]],
    base_policy: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """学习阈值（成本、延迟、失败率）"""
    
    if not examples:
        return _default_thresholds(base_policy)
    
    # 收集成本数据
    costs = [e.get("cost", {}).get("usd", 0.0) for e in examples if e.get("cost", {}).get("usd")]
    latencies = [
        e.get("cost", {}).get("latency_ms", 0) or 0
        for e in examples
        if e.get("cost", {}).get("latency_ms")
    ]
    
    # 计算失败率
    total_runs = len(examples)
    failed_runs = len([e for e in examples if e.get("outcome", {}).get("status") == "failed"])
    failure_rate = failed_runs / total_runs if total_runs > 0 else 0.0
    
    # 阈值规则（基于百分位数）
    max_cost_usd = 0.5  # 默认
    max_latency_ms = 3000  # 默认
    failure_rate_tolerance = 0.1  # 默认 10%
    
    if costs:
        # 使用 90% 分位数作为 max_cost 阈值
        sorted_costs = sorted(costs)
        p90_idx = int(len(sorted_costs) * 0.9)
        if p90_idx < len(sorted_costs):
            max_cost_usd = sorted_costs[p90_idx] * 1.5  # 放宽 1.5 倍
        else:
            max_cost_usd = max(costs) * 1.2
    
    if latencies:
        # 使用 90% 分位数作为 max_latency 阈值
        sorted_latencies = sorted(latencies)
        p90_idx = int(len(sorted_latencies) * 0.9)
        if p90_idx < len(sorted_latencies):
            max_latency_ms = sorted_latencies[p90_idx] * 1.5
        else:
            max_latency_ms = max(latencies) * 1.2
    
    # failure_rate_tolerance：基于观察到的失败率，设置稍高的容忍度
    if failure_rate > 0:
        failure_rate_tolerance = min(failure_rate * 1.5, 0.3)  # 最多容忍 30%
    
    # 如果有 base_policy，考虑平滑更新
    if base_policy and "thresholds" in base_policy:
        base_thresholds = base_policy["thresholds"]
        # 使用加权平均（新数据 70%，旧数据 30%）
        max_cost_usd = max_cost_usd * 0.7 + base_thresholds.get("max_cost_usd", 0.5) * 0.3
        max_latency_ms = max_latency_ms * 0.7 + base_thresholds.get("max_latency_ms", 3000) * 0.3
        failure_rate_tolerance = failure_rate_tolerance * 0.7 + base_thresholds.get("failure_rate_tolerance", 0.1) * 0.3
    
    return {
        "max_cost_usd": round(max_cost_usd, 4),
        "max_latency_ms": int(max_latency_ms),
        "failure_rate_tolerance": round(failure_rate_tolerance, 3)
    }


def _default_policy() -> Dict[str, Any]:
    """默认策略"""
    return {
        "policy_version": "v1",
        "plan_selection_rules": {
            "prefer_plan": "normal",
            "fallback_order": ["normal", "degraded", "minimal"]
        },
        "thresholds": _default_thresholds(None),
        "metadata": {
            "generated_at": datetime.now().timestamp(),
            "source_runs": 0
        }
    }


def _default_thresholds(base_policy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """默认阈值"""
    if base_policy and "thresholds" in base_policy:
        return base_policy["thresholds"].copy()
    return {
        "max_cost_usd": 0.5,
        "max_latency_ms": 3000,
        "failure_rate_tolerance": 0.1
    }


def _extract_version_number(version_str: str) -> int:
    """从版本字符串提取数字（例如 "v3" -> 3）"""
    try:
        if version_str.startswith("v"):
            return int(version_str[1:])
        return int(version_str)
    except (ValueError, AttributeError):
        return 1


def save_policy_artifact(
    policy: Dict[str, Any],
    output_dir: str
) -> str:
    """
    将 policy artifact 保存为 JSON 文件，
    返回文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    
    policy_version = policy.get("policy_version", "v1")
    filename = f"policy_{policy_version}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(policy, f, indent=2, ensure_ascii=False)
    
    return filepath

