"""
Shadow Evaluator: 影子评估器
在相同输入 traces 上，分别用 active/candidate policy 走一遍"可重放执行"
输出 metrics + delta + gate decision（但不切换版本）
"""
import os
import json
import random
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class ShadowMetrics:
    """影子评估指标"""
    success_rate: float
    avg_cost: float
    p95_latency: float  # 使用 step_count 近似（无真实延迟时）
    evidence_pass_rate: float
    total_runs: int
    success_count: int
    failed_count: int


@dataclass
class ShadowEvalReport:
    """影子评估报告"""
    active_policy: str
    candidate_policy: str
    eval_mode: str  # "shadow"
    dataset_ref: str
    n_runs: int
    metrics: Dict[str, Any]
    delta: Dict[str, float]
    decision: Dict[str, Any]
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowEvaluator:
    """
    影子评估器：在不影响线上输出的情况下对比 candidate vs active policy。
    
    工作流程：
    1. 从 TraceStore 拉取最近 N 个可评估 runs
    2. 对每个 run，分别用 active/candidate policy 执行模拟
    3. 收集指标并生成对比报告
    4. 不修改任何线上数据
    """
    
    def __init__(
        self,
        trace_store,
        execution_engine,
        policy_loader
    ):
        """
        初始化 Shadow Evaluator。
        
        Args:
            trace_store: TraceStore 实例
            execution_engine: ExecutionEngine 实例（用于获取 plan_selector）
            policy_loader: policy 加载函数（如 load_policy_artifact）
        """
        self.trace_store = trace_store
        self.execution_engine = execution_engine
        self.policy_loader = policy_loader
        self.eval_dir = "artifacts/evals"
        os.makedirs(self.eval_dir, exist_ok=True)
    
    def evaluate(
        self,
        active_policy_id: str,
        candidate_policy_id: str,
        max_runs: int = 300,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        在相同输入 traces 上，分别用 active/candidate 走一遍"可重放执行"。
        
        Args:
            active_policy_id: 当前活跃的 policy ID
            candidate_policy_id: 候选 policy ID
            max_runs: 最大评估 run 数
            seed: 随机种子（确保可复现）
            
        Returns:
            dict: Shadow Eval Report（包含 metrics + delta + gate decision）
        """
        random.seed(seed)
        
        # Step 1: 拉取可评估的 runs
        eval_runs = self._get_evaluable_runs(max_runs)
        
        if not eval_runs:
            return self._empty_report(active_policy_id, candidate_policy_id)
        
        # Step 2: 加载两个 policy
        active_policy = self._load_policy(active_policy_id)
        candidate_policy = self._load_policy(candidate_policy_id)
        
        if not active_policy or not candidate_policy:
            return self._empty_report(active_policy_id, candidate_policy_id)
        
        # Step 3: 对每个 run 进行影子评估
        active_results = []
        candidate_results = []
        
        for run_data in eval_runs:
            # 用 active policy 模拟执行
            active_result = self._simulate_run(run_data, active_policy)
            active_results.append(active_result)
            
            # 用 candidate policy 模拟执行
            candidate_result = self._simulate_run(run_data, candidate_policy)
            candidate_results.append(candidate_result)
        
        # Step 4: 计算指标
        active_metrics = self._calculate_metrics(active_results)
        candidate_metrics = self._calculate_metrics(candidate_results)
        
        # Step 5: 计算 delta
        delta = self._calculate_delta(active_metrics, candidate_metrics)
        
        # Step 6: 生成报告
        report = ShadowEvalReport(
            active_policy=active_policy_id,
            candidate_policy=candidate_policy_id,
            eval_mode="shadow",
            dataset_ref=f"trace_store:{len(eval_runs)}_runs",
            n_runs=len(eval_runs),
            metrics={
                "success_rate_active": active_metrics.success_rate,
                "success_rate_candidate": candidate_metrics.success_rate,
                "avg_cost_active": active_metrics.avg_cost,
                "avg_cost_candidate": candidate_metrics.avg_cost,
                "p95_latency_active": active_metrics.p95_latency,
                "p95_latency_candidate": candidate_metrics.p95_latency,
                "evidence_pass_rate_active": active_metrics.evidence_pass_rate,
                "evidence_pass_rate_candidate": candidate_metrics.evidence_pass_rate
            },
            delta={
                "success_rate": delta["success_rate"],
                "avg_cost": delta["avg_cost"],
                "p95_latency": delta["p95_latency"],
                "evidence_pass_rate": delta["evidence_pass_rate"]
            },
            decision={
                "gate_pass": None,  # 由 ABGate 决定
                "reasons": [],
                "blocked_reasons": []
            },
            created_at=datetime.now().isoformat()
        )
        
        # Step 7: 保存报告
        report_path = self._save_report(report)
        
        result = report.to_dict()
        result["report_path"] = report_path
        
        return result
    
    def _get_evaluable_runs(self, max_runs: int) -> List[Dict[str, Any]]:
        """获取可评估的 runs（包含 success 和 failure）"""
        eval_runs = []
        
        # 从 TraceStore 获取所有任务
        all_task_ids = self.trace_store.query_tasks({})
        
        # 如果索引为空，从 summaries 目录读取
        if not all_task_ids:
            summaries_dir = self.trace_store.summaries_dir
            if os.path.exists(summaries_dir):
                all_task_ids = [
                    f[:-5] for f in os.listdir(summaries_dir)
                    if f.endswith('.json')
                ]
        
        # 随机采样（确保可复现）
        random.shuffle(all_task_ids)
        selected_ids = all_task_ids[:max_runs]
        
        for task_id in selected_ids:
            summary = self.trace_store.load_summary(task_id)
            if not summary:
                continue
            
            # 加载 events
            events, _ = self.trace_store.load_events(task_id, limit=100)
            
            # 构建 run_data
            run_data = {
                "task_id": task_id,
                "summary": {
                    "state": summary.state,
                    "current_plan_id": summary.current_plan_id,
                    "current_plan_path_type": summary.current_plan_path_type,
                    "cost_summary": summary.cost_summary or {},
                    "result_summary": summary.result_summary or {},
                    "key_decisions_topk": summary.key_decisions_topk or []
                },
                "events": [
                    {
                        "type": e.type,
                        "payload": e.payload or {}
                    }
                    for e in events
                ],
                "created_at": summary.created_at,
                "updated_at": summary.updated_at
            }
            
            eval_runs.append(run_data)
        
        return eval_runs
    
    def _load_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """加载 policy artifact"""
        try:
            policy_path = os.path.join("artifacts/policies", f"policy_{policy_id}.json")
            if os.path.exists(policy_path):
                return self.policy_loader(policy_path)
            return None
        except Exception:
            return None
    
    def _simulate_run(
        self,
        run_data: Dict[str, Any],
        policy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用指定 policy 模拟执行一个 run。
        
        这是一个"干运行"（dry-run），不实际执行 agents，
        而是基于 policy 的规则预测执行路径和结果。
        
        注意：这里使用简化的模拟逻辑，基于 policy 的 plan_selection_rules
        和 thresholds 来预测结果。真实实现可以更复杂。
        """
        summary = run_data.get("summary", {})
        events = run_data.get("events", [])
        
        # 提取原始执行信息
        original_state = summary.get("state", "UNKNOWN")
        original_plan = summary.get("current_plan_id", "normal_v1")
        original_cost = summary.get("cost_summary", {}).get("total", 0.0)
        
        # 从 events 计算 step_count（用于近似 latency）
        step_count = len([e for e in events if e.get("type") == "agent_report"])
        
        # 从 events 检查 evidence_pass
        evidence_events = [e for e in events if e.get("type") == "governance_decision"]
        evidence_pass = not any(
            e.get("payload", {}).get("execution_mode") == "paused"
            for e in evidence_events
        )
        
        # 使用 policy 的规则预测结果
        plan_rules = policy.get("plan_selection_rules", {})
        thresholds = policy.get("thresholds", {})
        
        # 模拟 plan 选择
        prefer_plan = plan_rules.get("prefer_plan", "normal")
        
        # 模拟成本（基于 policy thresholds 调整）
        max_cost = thresholds.get("max_cost_usd", 0.5)
        simulated_cost = original_cost
        
        # 如果 policy 倾向于 degraded/minimal，可能降低成本
        if prefer_plan in ["degraded", "minimal"]:
            simulated_cost = original_cost * 0.8  # 降级路径成本降低 20%
        
        # 模拟成功/失败（基于原始状态和 policy 的 failure_rate_tolerance）
        failure_tolerance = thresholds.get("failure_rate_tolerance", 0.1)
        
        # 如果原始是失败的，模拟 policy 是否能改善
        is_success = original_state in ["COMPLETED", "SUCCESS"]
        
        # 简化逻辑：如果 policy 更严格（failure_tolerance 更低），可能更早拒绝
        # 如果 policy 更宽松，可能接受更多边缘情况
        simulated_success = is_success
        
        # 模拟 step_count 作为 latency 近似（毫秒）
        # 假设每个 step 平均 200ms
        simulated_latency = step_count * 200
        
        return {
            "task_id": run_data.get("task_id"),
            "is_success": simulated_success,
            "cost": simulated_cost,
            "latency": simulated_latency,
            "step_count": step_count,
            "evidence_pass": evidence_pass,
            "selected_plan": prefer_plan,
            "shadow_run": True  # 标记为影子运行
        }
    
    def _calculate_metrics(self, results: List[Dict[str, Any]]) -> ShadowMetrics:
        """计算指标"""
        if not results:
            return ShadowMetrics(
                success_rate=0.0,
                avg_cost=0.0,
                p95_latency=0.0,
                evidence_pass_rate=0.0,
                total_runs=0,
                success_count=0,
                failed_count=0
            )
        
        total = len(results)
        success_count = sum(1 for r in results if r.get("is_success"))
        failed_count = total - success_count
        
        # Success rate
        success_rate = success_count / total if total > 0 else 0.0
        
        # Average cost
        costs = [r.get("cost", 0.0) for r in results]
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        
        # P95 latency（使用 step_count * 200ms 近似）
        latencies = sorted([r.get("latency", 0) for r in results])
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_idx] if p95_idx < len(latencies) else (latencies[-1] if latencies else 0)
        
        # Evidence pass rate
        evidence_passes = sum(1 for r in results if r.get("evidence_pass", True))
        evidence_pass_rate = evidence_passes / total if total > 0 else 0.0
        
        return ShadowMetrics(
            success_rate=round(success_rate, 4),
            avg_cost=round(avg_cost, 4),
            p95_latency=round(p95_latency, 2),
            evidence_pass_rate=round(evidence_pass_rate, 4),
            total_runs=total,
            success_count=success_count,
            failed_count=failed_count
        )
    
    def _calculate_delta(
        self,
        active_metrics: ShadowMetrics,
        candidate_metrics: ShadowMetrics
    ) -> Dict[str, float]:
        """计算 candidate vs active 的差值"""
        return {
            "success_rate": round(candidate_metrics.success_rate - active_metrics.success_rate, 4),
            "avg_cost": round(candidate_metrics.avg_cost - active_metrics.avg_cost, 4),
            "p95_latency": round(candidate_metrics.p95_latency - active_metrics.p95_latency, 2),
            "evidence_pass_rate": round(candidate_metrics.evidence_pass_rate - active_metrics.evidence_pass_rate, 4)
        }
    
    def _save_report(self, report: ShadowEvalReport) -> str:
        """保存评估报告"""
        filename = f"shadow_eval_{report.candidate_policy}_vs_{report.active_policy}.json"
        report_path = os.path.join(self.eval_dir, filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        return report_path
    
    def _empty_report(
        self,
        active_policy_id: str,
        candidate_policy_id: str
    ) -> Dict[str, Any]:
        """生成空报告（无可评估数据时）"""
        return {
            "active_policy": active_policy_id,
            "candidate_policy": candidate_policy_id,
            "eval_mode": "shadow",
            "dataset_ref": "empty",
            "n_runs": 0,
            "metrics": {},
            "delta": {},
            "decision": {
                "gate_pass": False,
                "reasons": [],
                "blocked_reasons": ["no_evaluable_runs"]
            },
            "created_at": datetime.now().isoformat()
        }



