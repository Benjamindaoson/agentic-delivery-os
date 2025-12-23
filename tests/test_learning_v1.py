"""
Learning v1: 离线策略演化闭环的最小验证测试
"""
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from runtime.learning.dataset_builder import (
    build_training_examples,
    export_training_dataset
)
from runtime.learning.policy_trainer import (
    train_policy_from_examples,
    save_policy_artifact
)
from runtime.extensions.policy_pack import load_policy_artifact
from runtime.agent_registry.version_resolver import resolve_active_policy
from runtime.platform.trace_store import TraceStore, TraceSummary, TraceEvent


def test_learning_v1_full_cycle(tmp_path, monkeypatch):
    """测试完整的 Learning v1 流程：Trace → Dataset → Policy → Load"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    policy_dir = tmp_path / "artifacts" / "policies"
    dataset_dir = tmp_path / "artifacts" / "datasets"
    
    trace_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    dataset_dir.mkdir(parents=True)
    
    # Step 1: 创建 mock trace_store
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 mock trace 数据
    task_id = "test_task_001"
    
    # 创建 summary
    summary = TraceSummary(
        task_id=task_id,
        state="COMPLETED",
        current_plan_id="normal_v1",
        current_plan_path_type="normal",
        key_decisions_topk=[
            {
                "type": "governance_decision",
                "execution_mode": "normal",
                "reasoning": "All checks passed",
                "timestamp": datetime.now().isoformat()
            }
        ],
        cost_summary={
            "total": 0.45,
            "by_agent": {"Product": 0.1, "Data": 0.2, "Execution": 0.15}
        },
        result_summary={
            "final_state": "COMPLETED",
            "executed_agents_count": 3,
            "has_degraded": False,
            "has_paused": False
        },
        created_at=datetime.now().isoformat(),
        updated_at=(datetime.now() + timedelta(seconds=100)).isoformat()
    )
    trace_store.save_summary(summary)
    
    # 创建 events
    event = TraceEvent(
        event_id="event_001",
        task_id=task_id,
        ts=datetime.now().isoformat(),
        type="agent_report",
        payload={
            "agent_name": "Product",
            "signals": {"tokens_used": 1000},
            "cost_impact": 0.1
        }
    )
    trace_store.save_event(event)
    
    event2 = TraceEvent(
        event_id="event_002",
        task_id=task_id,
        ts=datetime.now().isoformat(),
        type="governance_decision",
        payload={
            "execution_mode": "normal",
            "reasoning": "All checks passed"
        }
    )
    trace_store.save_event(event2)
    
    # 创建索引
    trace_data_mock = {
        "state_transitions": [{"state": "COMPLETED"}],
        "agent_reports": [
            {"agent_name": "Product", "signals": {"tokens_used": 1000}, "cost_impact": 0.1},
            {"agent_name": "Data", "signals": {"tokens_used": 2000}, "cost_impact": 0.2},
            {"agent_name": "Execution", "signals": {"tokens_used": 1500}, "cost_impact": 0.15}
        ],
        "governance_decisions": [
            {"execution_mode": "normal", "reasoning": "All checks passed"}
        ],
        "execution_plan": {
            "plan_id": "normal_v1",
            "plan_version": "1.0",
            "path_type": "normal"
        },
        "generated_at": datetime.now().isoformat()
    }
    trace_store.index_trace(task_id, trace_data_mock)
    
    # Step 2: 构建训练样本
    examples = build_training_examples(
        trace_store,
        max_examples=100
    )
    
    assert len(examples) > 0, "应该生成至少一个训练样本"
    
    example = examples[0]
    assert "run_id" in example
    assert "selected_plan" in example
    assert "governance" in example
    assert "outcome" in example
    assert "cost" in example
    assert "timestamps" in example
    
    # Step 3: 导出训练数据集
    dataset_path = dataset_dir / "training_examples.jsonl"
    export_training_dataset(examples, str(dataset_path))
    
    assert dataset_path.exists(), "训练数据集文件应该被创建"
    
    # 验证 JSONL 格式
    with open(dataset_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) > 0
        parsed = json.loads(lines[0])
        assert "run_id" in parsed
    
    # Step 4: 训练 policy
    policy = train_policy_from_examples(examples)
    
    assert "policy_version" in policy
    assert "plan_selection_rules" in policy
    assert "thresholds" in policy
    assert "metadata" in policy
    
    assert policy["plan_selection_rules"]["prefer_plan"] in ["normal", "degraded", "minimal"]
    assert "max_cost_usd" in policy["thresholds"]
    assert "max_latency_ms" in policy["thresholds"]
    assert "failure_rate_tolerance" in policy["thresholds"]
    
    # Step 5: 保存 policy artifact
    policy_path = save_policy_artifact(policy, str(policy_dir))
    
    assert os.path.exists(policy_path), "Policy artifact 文件应该被创建"
    
    # Step 6: 加载 policy artifact
    loaded_policy = load_policy_artifact(policy_path)
    
    assert loaded_policy["policy_version"] == policy["policy_version"]
    assert loaded_policy["plan_selection_rules"] == policy["plan_selection_rules"]
    assert loaded_policy["thresholds"] == policy["thresholds"]
    
    # Step 7: 通过 version_resolver 解析 active policy
    active_policy = resolve_active_policy(
        policy_dir=str(policy_dir),
        config=None
    )
    
    assert active_policy is not None
    assert "policy_version" in active_policy
    assert active_policy["policy_version"] == policy["policy_version"], \
        "应该解析到最新训练的 policy"
    
    print("✅ Learning v1 完整流程测试通过")


def test_policy_version_rollback(tmp_path, monkeypatch):
    """测试 policy 版本回滚功能"""
    monkeypatch.chdir(tmp_path)
    
    policy_dir = tmp_path / "artifacts" / "policies"
    policy_dir.mkdir(parents=True)
    
    # 创建 v1 policy
    policy_v1 = {
        "policy_version": "v1",
        "plan_selection_rules": {"prefer_plan": "normal"},
        "thresholds": {"max_cost_usd": 0.5},
        "metadata": {"source_runs": 10}
    }
    save_policy_artifact(policy_v1, str(policy_dir))
    
    # 创建 v2 policy
    policy_v2 = {
        "policy_version": "v2",
        "plan_selection_rules": {"prefer_plan": "degraded"},
        "thresholds": {"max_cost_usd": 0.3},
        "metadata": {"source_runs": 20}
    }
    save_policy_artifact(policy_v2, str(policy_dir))
    
    # 测试解析最新版本
    active_policy = resolve_active_policy(policy_dir=str(policy_dir))
    assert active_policy["policy_version"] == "v2"
    
    # 测试通过环境变量指定版本
    import os
    os.environ["ACTIVE_POLICY_VERSION"] = "v1"
    try:
        active_policy = resolve_active_policy(policy_dir=str(policy_dir))
        assert active_policy["policy_version"] == "v1"
    finally:
        os.environ.pop("ACTIVE_POLICY_VERSION", None)
    
    # 测试通过 config 指定版本
    active_policy = resolve_active_policy(
        policy_dir=str(policy_dir),
        config={"active_policy_version": "v1"}
    )
    assert active_policy["policy_version"] == "v1"
    
    print("✅ Policy 版本回滚测试通过")


def test_policy_trainer_statistics(tmp_path, monkeypatch):
    """测试 policy trainer 的统计功能"""
    monkeypatch.chdir(tmp_path)
    
    # 创建混合成功/失败的样本
    examples = [
        {
            "run_id": "run1",
            "selected_plan": {"plan_id": "normal_v1", "version": "1.0"},
            "governance": {"final_decision": "allow"},
            "outcome": {"status": "success"},
            "cost": {"tokens": 5000, "usd": 0.25, "latency_ms": 2000}
        },
        {
            "run_id": "run2",
            "selected_plan": {"plan_id": "degraded_v1", "version": "1.0"},
            "governance": {"final_decision": "degrade"},
            "outcome": {"status": "degraded"},
            "cost": {"tokens": 3000, "usd": 0.15, "latency_ms": 1500}
        },
        {
            "run_id": "run3",
            "selected_plan": {"plan_id": "normal_v1", "version": "1.0"},
            "governance": {"final_decision": "allow"},
            "outcome": {"status": "failed"},
            "cost": {"tokens": 8000, "usd": 0.8, "latency_ms": 5000}
        }
    ]
    
    # 训练 policy
    policy = train_policy_from_examples(examples)
    
    # 验证统计信息
    assert policy["metadata"]["source_runs"] == 3
    assert "success_rate" in policy["metadata"]
    assert "failure_rate" in policy["metadata"]
    assert policy["metadata"]["success_rate"] == 1.0 / 3.0
    assert policy["metadata"]["failure_rate"] == 1.0 / 3.0
    
    # 验证阈值学习（应该基于数据）
    assert policy["thresholds"]["max_cost_usd"] > 0
    assert policy["thresholds"]["max_latency_ms"] > 0
    
    print("✅ Policy trainer 统计功能测试通过")

