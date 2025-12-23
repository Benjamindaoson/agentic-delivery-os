"""
Shadow Eval 和 A/B Gate 测试
"""
import os
import json
from datetime import datetime
from runtime.evaluation.shadow.shadow_evaluator import ShadowEvaluator
from runtime.rollout.ab_gate import ABGate
from runtime.platform.trace_store import TraceStore, TraceSummary, TraceEvent
from runtime.learning.policy_trainer import save_policy_artifact
from runtime.extensions.policy_pack import load_policy_artifact


def test_shadow_eval_basic(tmp_path, monkeypatch):
    """测试 Shadow Eval 基本功能"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    eval_dir = tmp_path / "artifacts" / "evals"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    eval_dir.mkdir(parents=True)
    
    # 创建 TraceStore 并填充 mock 数据
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    for i in range(100):
        task_id = f"task_{i:04d}"
        state = "FAILED" if i % 10 == 0 else "COMPLETED"  # 10% 失败率
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            cost_summary={"total": 0.3},
            result_summary={"final_state": state},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
        
        # 创建 events
        event = TraceEvent(
            event_id=f"event_{i}",
            task_id=task_id,
            ts=datetime.now().isoformat(),
            type="agent_report",
            payload={"agent_name": "Product"}
        )
        trace_store.save_event(event)
        
        event2 = TraceEvent(
            event_id=f"event_{i}_2",
            task_id=task_id,
            ts=datetime.now().isoformat(),
            type="governance_decision",
            payload={"execution_mode": "normal"}
        )
        trace_store.save_event(event2)
    
    # 创建 active policy (v1)
    policy_v1 = {
        "policy_version": "v1",
        "plan_selection_rules": {"prefer_plan": "normal"},
        "thresholds": {"max_cost_usd": 0.5, "failure_rate_tolerance": 0.1},
        "metadata": {"source_runs": 0}
    }
    save_policy_artifact(policy_v1, str(policy_dir))
    
    # 创建 candidate policy (v2)
    policy_v2 = {
        "policy_version": "v2",
        "plan_selection_rules": {"prefer_plan": "degraded"},
        "thresholds": {"max_cost_usd": 0.3, "failure_rate_tolerance": 0.08},
        "metadata": {"source_runs": 100}
    }
    save_policy_artifact(policy_v2, str(policy_dir))
    
    # 初始化 ShadowEvaluator
    shadow_evaluator = ShadowEvaluator(
        trace_store=trace_store,
        execution_engine=None,  # 不需要真实 execution_engine
        policy_loader=load_policy_artifact
    )
    
    # 执行评估
    report = shadow_evaluator.evaluate(
        active_policy_id="v1",
        candidate_policy_id="v2",
        max_runs=50,
        seed=42
    )
    
    # 验证报告结构
    assert "active_policy" in report
    assert "candidate_policy" in report
    assert "metrics" in report
    assert "delta" in report
    assert "n_runs" in report
    
    assert report["active_policy"] == "v1"
    assert report["candidate_policy"] == "v2"
    assert report["n_runs"] <= 50
    
    # 验证 metrics 结构
    metrics = report["metrics"]
    assert "success_rate_active" in metrics
    assert "success_rate_candidate" in metrics
    assert "avg_cost_active" in metrics
    assert "avg_cost_candidate" in metrics
    assert "p95_latency_active" in metrics
    assert "p95_latency_candidate" in metrics
    assert "evidence_pass_rate_active" in metrics
    assert "evidence_pass_rate_candidate" in metrics
    
    # 验证 delta 结构
    delta = report["delta"]
    assert "success_rate" in delta
    assert "avg_cost" in delta
    assert "p95_latency" in delta
    assert "evidence_pass_rate" in delta
    
    print("✅ Shadow Eval 基本功能测试通过")


def test_ab_gate_pass(tmp_path, monkeypatch):
    """测试 A/B Gate 通过情况"""
    monkeypatch.chdir(tmp_path)
    
    # 构造一个 candidate 优于 active 的 shadow_report
    shadow_report = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "metrics": {
            "success_rate_active": 0.85,
            "success_rate_candidate": 0.88,  # +3%
            "avg_cost_active": 0.40,
            "avg_cost_candidate": 0.38,  # -5%
            "p95_latency_active": 1000,
            "p95_latency_candidate": 950,  # -5%
            "evidence_pass_rate_active": 0.95,
            "evidence_pass_rate_candidate": 0.96  # +1%
        }
    }
    
    ab_gate = ABGate(
        min_success_uplift=0.00,
        max_cost_increase=0.05,
        max_latency_increase_p95=0.10,
        min_evidence_pass_rate=0.90
    )
    
    decision = ab_gate.decide(shadow_report)
    
    # 应该通过
    assert decision["gate_pass"] is True
    assert len(decision["blocked_reasons"]) == 0
    assert len(decision["reasons"]) > 0
    
    # 验证所有检查都通过
    assert decision["checks"]["success_rate"] is True
    assert decision["checks"]["avg_cost"] is True
    assert decision["checks"]["p95_latency"] is True
    assert decision["checks"]["evidence_pass_rate"] is True
    
    print("✅ A/B Gate 通过测试通过")


def test_ab_gate_blocked_by_success_rate(tmp_path, monkeypatch):
    """测试 A/B Gate 因 success_rate 下降被阻止"""
    monkeypatch.chdir(tmp_path)
    
    # 构造一个 candidate success_rate 下降的 shadow_report
    shadow_report = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "metrics": {
            "success_rate_active": 0.90,
            "success_rate_candidate": 0.85,  # -5%（下降）
            "avg_cost_active": 0.40,
            "avg_cost_candidate": 0.38,
            "p95_latency_active": 1000,
            "p95_latency_candidate": 950,
            "evidence_pass_rate_active": 0.95,
            "evidence_pass_rate_candidate": 0.96
        }
    }
    
    ab_gate = ABGate(
        min_success_uplift=0.00,  # 不允许下降
        max_cost_increase=0.05,
        max_latency_increase_p95=0.10,
        min_evidence_pass_rate=0.90
    )
    
    decision = ab_gate.decide(shadow_report)
    
    # 不应该通过
    assert decision["gate_pass"] is False
    assert len(decision["blocked_reasons"]) > 0
    assert decision["checks"]["success_rate"] is False
    
    print("✅ A/B Gate 因 success_rate 下降被阻止测试通过")


def test_ab_gate_blocked_by_cost_increase(tmp_path, monkeypatch):
    """测试 A/B Gate 因 cost 增加过多被阻止"""
    monkeypatch.chdir(tmp_path)
    
    # 构造一个 candidate cost 增加超过阈值的 shadow_report
    shadow_report = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "metrics": {
            "success_rate_active": 0.85,
            "success_rate_candidate": 0.88,
            "avg_cost_active": 0.40,
            "avg_cost_candidate": 0.50,  # +25%（超过 5% 阈值）
            "p95_latency_active": 1000,
            "p95_latency_candidate": 950,
            "evidence_pass_rate_active": 0.95,
            "evidence_pass_rate_candidate": 0.96
        }
    }
    
    ab_gate = ABGate(
        min_success_uplift=0.00,
        max_cost_increase=0.05,  # 最多允许 5% 增加
        max_latency_increase_p95=0.10,
        min_evidence_pass_rate=0.90
    )
    
    decision = ab_gate.decide(shadow_report)
    
    # 不应该通过
    assert decision["gate_pass"] is False
    assert len(decision["blocked_reasons"]) > 0
    assert decision["checks"]["avg_cost"] is False
    
    print("✅ A/B Gate 因 cost 增加过多被阻止测试通过")


def test_ab_gate_blocked_by_evidence_pass_rate(tmp_path, monkeypatch):
    """测试 A/B Gate 因 evidence_pass_rate 不足被阻止"""
    monkeypatch.chdir(tmp_path)
    
    # 构造一个 candidate evidence_pass_rate 不足的 shadow_report
    shadow_report = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "metrics": {
            "success_rate_active": 0.85,
            "success_rate_candidate": 0.88,
            "avg_cost_active": 0.40,
            "avg_cost_candidate": 0.38,
            "p95_latency_active": 1000,
            "p95_latency_candidate": 950,
            "evidence_pass_rate_active": 0.95,
            "evidence_pass_rate_candidate": 0.85  # 低于 90% 阈值
        }
    }
    
    ab_gate = ABGate(
        min_success_uplift=0.00,
        max_cost_increase=0.05,
        max_latency_increase_p95=0.10,
        min_evidence_pass_rate=0.90  # 最低 90%
    )
    
    decision = ab_gate.decide(shadow_report)
    
    # 不应该通过
    assert decision["gate_pass"] is False
    assert len(decision["blocked_reasons"]) > 0
    assert decision["checks"]["evidence_pass_rate"] is False
    
    print("✅ A/B Gate 因 evidence_pass_rate 不足被阻止测试通过")



