"""
L5 Pipeline: 工程化策略演化闭环入口
Shadow Eval → A/B Gate → Gradual Rollout → Auto-Rollback → 可审计记录
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

from runtime.learning.learning_controller import LearningController
from runtime.evaluation.shadow.shadow_evaluator import ShadowEvaluator
from runtime.rollout.ab_gate import ABGate
from runtime.rollout.rollout_manager import RolloutManager
from runtime.rollout.policy_router import PolicyRouter
from runtime.monitoring.policy_kpis.kpi_collector import PolicyKPICollector
from runtime.extensions.policy_pack import load_policy_artifact
from runtime.agent_registry.version_resolver import resolve_active_policy


def maybe_train_and_rollout(
    trace_store,
    execution_engine,
    *,
    force_train: bool = False
) -> Dict[str, Any]:
    """
    L5 Pipeline 入口：自动执行策略演化闭环。
    
    1) 检查是否有 rollout 在进行 -> 只做 KPI 检查与 advance/rollback
    2) 若 idle -> 考虑训练+shadow+gate
    3) 如果触发 Learning v1 生成 candidate policy
    4) ShadowEvaluator.evaluate(active, candidate)
    5) ABGate.decide(report)
    6) gate pass -> RolloutManager.start_canary()
    7) gate fail -> 记录报告并停止
    
    Args:
        trace_store: TraceStore 实例
        execution_engine: ExecutionEngine 实例
        force_train: 强制训练（跳过 should_train 检查）
        
    Returns:
        dict: L5 Pipeline 执行摘要
    """
    pipeline_start = datetime.now()
    audit_log_path = "artifacts/rollouts/audit_log.jsonl"
    
    try:
        # 初始化组件
        kpi_collector = PolicyKPICollector(trace_store)
        rollout_manager = RolloutManager(
            trace_store=trace_store,
            kpi_collector=kpi_collector
        )
        policy_router = PolicyRouter()
        
        # Step 1: 检查当前 rollout 状态
        current_stage = policy_router.get_current_stage()
        
        if current_stage in ["canary", "partial"]:
            # 有 rollout 在进行，只做 KPI 检查与 advance/rollback
            result = rollout_manager.check_and_maybe_advance_or_rollback()
            
            summary = {
                "action": "rollout_check",
                "result": result,
                "current_stage": current_stage,
                "timestamp": pipeline_start.isoformat()
            }
            
            _append_audit_log(audit_log_path, summary)
            return summary
        
        # Step 2: 检查是否需要训练新 policy
        learning_controller = LearningController(
            trace_store=trace_store,
            policy_dir="artifacts/policies"
        )
        
        if not force_train and not learning_controller.should_train():
            return {
                "action": "skip",
                "reason": "training_not_needed",
                "timestamp": pipeline_start.isoformat()
            }
        
        # Step 3: 执行 Learning v1 生成 candidate policy
        learning_summary = learning_controller.run_learning_pipeline()
        
        if not learning_summary.get("success"):
            summary = {
                "action": "training_failed",
                "reason": learning_summary.get("reason"),
                "error": learning_summary.get("error"),
                "timestamp": pipeline_start.isoformat()
            }
            _append_audit_log(audit_log_path, summary)
            return summary
        
        candidate_policy_id = learning_summary.get("policy_version")
        
        # Step 4: 获取当前 active policy
        try:
            active_policy = resolve_active_policy()
            active_policy_id = active_policy.get("policy_version", "v1")
        except Exception:
            active_policy_id = "v1"
        
        # 如果 candidate 和 active 是同一个版本，跳过
        if candidate_policy_id == active_policy_id:
            return {
                "action": "skip",
                "reason": "candidate_same_as_active",
                "policy_version": candidate_policy_id,
                "timestamp": pipeline_start.isoformat()
            }
        
        # Step 5: Shadow Evaluation
        shadow_evaluator = ShadowEvaluator(
            trace_store=trace_store,
            execution_engine=execution_engine,
            policy_loader=load_policy_artifact
        )
        
        shadow_report = shadow_evaluator.evaluate(
            active_policy_id=active_policy_id,
            candidate_policy_id=candidate_policy_id,
            max_runs=300,
            seed=42
        )
        
        # Step 6: A/B Gate 决策
        ab_gate = ABGate(
            min_success_uplift=0.00,
            max_cost_increase=0.05,
            max_latency_increase_p95=0.10,
            min_evidence_pass_rate=0.90
        )
        
        gate_decision = ab_gate.decide(shadow_report)
        
        # 更新 shadow_report 的 decision
        shadow_report["decision"] = gate_decision
        
        # Step 7: 根据 gate 决策行动
        if gate_decision.get("gate_pass"):
            # Gate 通过，启动 canary
            rollout_result = rollout_manager.start_canary(
                active=active_policy_id,
                candidate=candidate_policy_id,
                canary_pct=0.05
            )
            
            summary = {
                "action": "start_canary",
                "active_policy": active_policy_id,
                "candidate_policy": candidate_policy_id,
                "learning_summary": {
                    "training_examples": learning_summary.get("training_examples_count"),
                    "policy_path": learning_summary.get("policy_path")
                },
                "shadow_report": {
                    "n_runs": shadow_report.get("n_runs"),
                    "delta": shadow_report.get("delta"),
                    "report_path": shadow_report.get("report_path")
                },
                "gate_decision": gate_decision,
                "rollout_result": rollout_result,
                "timestamp": pipeline_start.isoformat()
            }
        else:
            # Gate 未通过，记录并停止
            summary = {
                "action": "gate_blocked",
                "active_policy": active_policy_id,
                "candidate_policy": candidate_policy_id,
                "learning_summary": {
                    "training_examples": learning_summary.get("training_examples_count"),
                    "policy_path": learning_summary.get("policy_path")
                },
                "shadow_report": {
                    "n_runs": shadow_report.get("n_runs"),
                    "delta": shadow_report.get("delta"),
                    "report_path": shadow_report.get("report_path")
                },
                "gate_decision": gate_decision,
                "timestamp": pipeline_start.isoformat()
            }
        
        _append_audit_log(audit_log_path, summary)
        return summary
    
    except Exception as e:
        # 任何异常不能影响主路径
        summary = {
            "action": "error",
            "error": str(e),
            "timestamp": pipeline_start.isoformat()
        }
        try:
            _append_audit_log(audit_log_path, summary)
        except Exception:
            pass
        return summary


def get_policy_for_run(run_context: Dict[str, Any]) -> str:
    """
    获取当前 run 应使用的 policy_id。
    
    这是 ExecutionEngine 应该调用的接口，用于支持灰度流量分配。
    
    Args:
        run_context: 运行上下文（包含 task_id 等）
        
    Returns:
        str: policy_id
    """
    policy_router = PolicyRouter()
    return policy_router.pick_policy(run_context)


def _append_audit_log(audit_log_path: str, entry: Dict[str, Any]) -> None:
    """追加审计日志"""
    os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
    
    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")



