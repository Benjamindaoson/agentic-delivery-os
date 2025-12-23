"""
Learning Controller 测试：验证自动触发机制
"""
import os
import json
import tempfile
from datetime import datetime, timedelta
from runtime.learning.learning_controller import LearningController
from runtime.platform.trace_store import TraceStore, TraceSummary, TraceEvent


def test_should_train_condition_a(tmp_path, monkeypatch):
    """测试触发条件 A：total_runs >= min_runs AND failure_rate > max_failure_rate"""
    monkeypatch.chdir(tmp_path)
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 600 个 runs，其中 100 个失败（failure_rate = 16.7%）
    for i in range(600):
        task_id = f"task_{i:04d}"
        state = "FAILED" if i < 100 else "COMPLETED"
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
        trace_store.index_trace(task_id, {"state_transitions": [{"state": state}]})
    
    # 初始化 controller
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=500,
        max_failure_rate=0.15,
        min_runs_between_training=1000
    )
    
    # 应该触发训练（total_runs=600 >= 500, failure_rate=16.7% > 15%）
    assert controller.should_train() is True
    
    print("✅ 触发条件 A 测试通过")


def test_should_train_condition_b(tmp_path, monkeypatch):
    """测试触发条件 B：距上次训练的 run 数 >= min_runs_between_training"""
    monkeypatch.chdir(tmp_path)
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 1500 个成功的 runs（failure_rate 低）
    for i in range(1500):
        task_id = f"task_{i:04d}"
        summary = TraceSummary(
            task_id=task_id,
            state="COMPLETED",
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
        trace_store.index_trace(task_id, {"state_transitions": [{"state": "COMPLETED"}]})
    
    # 记录上次训练在 400 runs 时
    metadata = {
        "policy_version": "v1",
        "trained_at": (datetime.now() - timedelta(days=7)).isoformat(),
        "total_runs_at_training": 400,
        "failure_rate_at_training": 0.05
    }
    metadata_path = policy_dir / "training_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)
    
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=500,
        max_failure_rate=0.15,
        min_runs_between_training=1000
    )
    
    # 应该触发训练（1500 - 400 = 1100 >= 1000）
    assert controller.should_train() is True
    
    print("✅ 触发条件 B 测试通过")


def test_should_not_train_insufficient_runs(tmp_path, monkeypatch):
    """测试不触发：run 数不足"""
    monkeypatch.chdir(tmp_path)
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 只有 300 个 runs（不足 min_runs=500）
    for i in range(300):
        task_id = f"task_{i:04d}"
        summary = TraceSummary(
            task_id=task_id,
            state="COMPLETED",
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=500,
        max_failure_rate=0.15,
        min_runs_between_training=1000
    )
    
    # 不应该触发训练
    assert controller.should_train() is False
    
    print("✅ 不触发测试通过（run 数不足）")


def test_run_learning_pipeline_full_cycle(tmp_path, monkeypatch):
    """测试完整的学习流程：Trace → Dataset → Policy → Rollout"""
    monkeypatch.chdir(tmp_path)
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建足够的 runs（包含成功和失败）
    for i in range(600):
        task_id = f"task_{i:04d}"
        state = "FAILED" if i % 10 == 0 else "COMPLETED"  # 10% 失败率
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            key_decisions_topk=[
                {
                    "type": "governance_decision",
                    "execution_mode": "normal",
                    "reasoning": "All checks passed"
                }
            ],
            cost_summary={"total": 0.3, "by_agent": {"Product": 0.1, "Execution": 0.2}},
            result_summary={
                "final_state": state,
                "executed_agents_count": 2,
                "has_degraded": False
            },
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
            payload={"agent_name": "Product", "signals": {"tokens_used": 1000}, "cost_impact": 0.1}
        )
        trace_store.save_event(event)
        
        trace_store.index_trace(task_id, {
            "state_transitions": [{"state": state}],
            "agent_reports": [{"agent_name": "Product", "signals": {"tokens_used": 1000}, "cost_impact": 0.1}],
            "governance_decisions": [{"execution_mode": "normal"}],
            "execution_plan": {"plan_id": "normal_v1", "path_type": "normal"},
            "generated_at": datetime.now().isoformat()
        })
    
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=500,
        max_failure_rate=0.15,
        min_runs_between_training=1000
    )
    
    # 执行学习流程
    summary = controller.run_learning_pipeline()
    
    # 验证结果
    assert summary["success"] is True
    assert "policy_version" in summary
    assert summary["training_examples_count"] > 0
    assert "policy_path" in summary
    
    # 验证 policy 文件已生成
    policy_version = summary["policy_version"]
    policy_path = policy_dir / f"policy_{policy_version}.json"
    assert policy_path.exists()
    
    # 验证 policy 内容
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = json.load(f)
    
    assert policy["policy_version"] == policy_version
    assert "plan_selection_rules" in policy
    assert "thresholds" in policy
    assert "metadata" in policy
    
    # 验证 training_metadata 已记录
    metadata_path = policy_dir / "training_metadata.json"
    assert metadata_path.exists()
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    assert metadata["policy_version"] == policy_version
    assert metadata["total_runs_at_training"] == 600
    
    print("✅ 完整学习流程测试通过")


def test_learning_does_not_affect_execution_engine(tmp_path, monkeypatch):
    """测试学习流程不影响 ExecutionEngine 的正常行为"""
    monkeypatch.chdir(tmp_path)
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 模拟 ExecutionEngine 行为：完成一个 run
    task_id = "test_task"
    
    # ExecutionEngine 写入 system_trace.json
    artifact_dir = tmp_path / "artifacts" / "rag_project" / task_id
    artifact_dir.mkdir(parents=True)
    
    trace_data = {
        "task_id": task_id,
        "state_transitions": [{"state": "COMPLETED"}],
        "agent_reports": [],
        "governance_decisions": [{"execution_mode": "normal"}],
        "execution_plan": {"plan_id": "normal_v1", "path_type": "normal"},
        "generated_at": datetime.now().isoformat()
    }
    
    trace_path = artifact_dir / "system_trace.json"
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f)
    
    # 初始化 controller（模拟 ExecutionEngine 内部的 learning_controller）
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=10,  # 低阈值，确保会触发
        max_failure_rate=0.0,
        min_runs_between_training=5
    )
    
    # 创建足够的 runs 触发学习
    for i in range(15):
        tid = f"task_{i:04d}"
        summary = TraceSummary(
            task_id=tid,
            state="COMPLETED",
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    # 模拟 _trigger_learning_if_needed 的调用（不会抛出异常）
    try:
        if controller.should_train():
            summary = controller.run_learning_pipeline()
            # 即使学习失败，也不影响主流程
            assert summary is not None
    except Exception as e:
        # 学习流程异常不应该传播到 ExecutionEngine
        assert False, f"学习流程不应该抛出异常: {e}"
    
    print("✅ 学习流程独立性测试通过")


def test_policy_version_rollout(tmp_path, monkeypatch):
    """测试 policy 版本自动切换（rollout）"""
    monkeypatch.chdir(tmp_path)
    
    from runtime.agent_registry.version_resolver import resolve_active_policy
    
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建初始 policy v1
    policy_v1 = {
        "policy_version": "v1",
        "plan_selection_rules": {"prefer_plan": "normal"},
        "thresholds": {"max_cost_usd": 0.5},
        "metadata": {"source_runs": 0}
    }
    from runtime.learning.policy_trainer import save_policy_artifact
    save_policy_artifact(policy_v1, str(policy_dir))
    
    # 验证初始 active policy 是 v1
    active_policy = resolve_active_policy(policy_dir=str(policy_dir))
    assert active_policy["policy_version"] == "v1"
    
    # 创建足够的 runs 触发学习
    for i in range(600):
        task_id = f"task_{i:04d}"
        summary = TraceSummary(
            task_id=task_id,
            state="COMPLETED",
            current_plan_id="normal_v1",
            current_plan_path_type="normal",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
        
        trace_store.index_trace(task_id, {
            "state_transitions": [{"state": "COMPLETED"}],
            "agent_reports": [{"agent_name": "Product", "cost_impact": 0.1}],
            "governance_decisions": [{"execution_mode": "normal"}],
            "execution_plan": {"plan_id": "normal_v1", "path_type": "normal"},
            "generated_at": datetime.now().isoformat()
        })
    
    controller = LearningController(
        trace_store=trace_store,
        policy_dir=str(policy_dir),
        min_runs=500,
        max_failure_rate=0.15,
        min_runs_between_training=1000
    )
    
    # 执行学习流程（生成 v2）
    summary = controller.run_learning_pipeline()
    assert summary["success"] is True
    assert summary["policy_version"] == "v2"
    
    # 验证 active policy 自动切换到 v2
    active_policy = resolve_active_policy(policy_dir=str(policy_dir))
    assert active_policy["policy_version"] == "v2"
    
    # 验证 v1 仍然存在（支持回滚）
    policy_v1_path = policy_dir / "policy_v1.json"
    assert policy_v1_path.exists()
    
    print("✅ Policy 版本自动切换测试通过")



