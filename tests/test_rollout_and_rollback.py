"""
Rollout 和 Rollback 测试
"""
import os
import json
from datetime import datetime
from runtime.rollout.rollout_manager import RolloutManager
from runtime.rollout.rollback_manager import RollbackManager
from runtime.rollout.policy_router import PolicyRouter
from runtime.monitoring.policy_kpis.kpi_collector import PolicyKPICollector
from runtime.platform.trace_store import TraceStore, TraceSummary, TraceEvent
from runtime.learning.policy_trainer import save_policy_artifact


def test_start_canary(tmp_path, monkeypatch):
    """测试 start_canary - traffic_split 正确"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    trace_dir.mkdir(parents=True)
    rollouts_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    kpi_collector = PolicyKPICollector(trace_store)
    
    rollout_manager = RolloutManager(
        trace_store=trace_store,
        kpi_collector=kpi_collector,
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    # 启动 canary
    result = rollout_manager.start_canary(
        active="v1",
        candidate="v2",
        canary_pct=0.05
    )
    
    assert result["success"] is True
    assert result["stage"] == "canary"
    assert result["traffic_split"]["v1"] == 0.95
    assert result["traffic_split"]["v2"] == 0.05
    
    # 验证状态文件
    state = rollout_manager.load_state()
    assert state["stage"] == "canary"
    assert state["active_policy"] == "v1"
    assert state["candidate_policy"] == "v2"
    
    print("✅ start_canary 测试通过")


def test_advance_stage_canary_to_partial(tmp_path, monkeypatch):
    """测试 advance_stage: canary -> partial (5% -> 25%)"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    trace_dir.mkdir(parents=True)
    rollouts_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建足够的 mock 数据让 KPI 通过
    for i in range(300):
        task_id = f"task_{i:04d}"
        plan_id = "v2" if i % 20 == 0 else "v1"  # 5% 使用 v2
        state = "COMPLETED"  # 全部成功
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id=plan_id,
            current_plan_path_type="normal",
            cost_summary={"total": 0.3},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    kpi_collector = PolicyKPICollector(trace_store)
    
    rollout_manager = RolloutManager(
        trace_store=trace_store,
        kpi_collector=kpi_collector,
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    # 先启动 canary
    rollout_manager.start_canary(active="v1", candidate="v2", canary_pct=0.05)
    
    # 推进到 partial
    result = rollout_manager.advance_stage()
    
    assert result["success"] is True
    assert result["from_stage"] == "canary"
    assert result["to_stage"] == "partial"
    assert result["traffic_split"]["v2"] == 0.25
    assert result["traffic_split"]["v1"] == 0.75
    
    print("✅ advance_stage canary -> partial 测试通过")


def test_advance_stage_partial_to_full(tmp_path, monkeypatch):
    """测试 advance_stage: partial -> full (25% -> 100%)"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    trace_dir.mkdir(parents=True)
    rollouts_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 mock 数据
    for i in range(300):
        task_id = f"task_{i:04d}"
        plan_id = "v2" if i % 4 == 0 else "v1"  # 25% 使用 v2
        state = "COMPLETED"
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id=plan_id,
            current_plan_path_type="normal",
            cost_summary={"total": 0.3},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    kpi_collector = PolicyKPICollector(trace_store)
    
    rollout_manager = RolloutManager(
        trace_store=trace_store,
        kpi_collector=kpi_collector,
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    # 手动设置状态为 partial
    state = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "stage": "partial",
        "traffic_split": {"v1": 0.75, "v2": 0.25},
        "started_at": datetime.now().isoformat(),
        "last_checked_at": datetime.now().isoformat(),
        "kpi_window": {"n_runs": 200, "lookback_minutes": 60},
        "thresholds": {
            "min_success_uplift": 0.00,
            "max_cost_increase": 0.05,
            "max_failure_rate": 0.15
        }
    }
    rollout_manager.save_state(state)
    
    # 推进到 full
    result = rollout_manager.advance_stage()
    
    assert result["success"] is True
    assert result["from_stage"] == "partial"
    assert result["to_stage"] == "full"
    # full 阶段：candidate 成为 active
    assert result["active_policy"] == "v2"
    assert result["traffic_split"]["v2"] == 1.0
    
    print("✅ advance_stage partial -> full 测试通过")


def test_rollback_on_kpi_failure(tmp_path, monkeypatch):
    """测试 KPI 不达标触发 rollback"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    trace_dir.mkdir(parents=True)
    rollouts_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 mock 数据，v2 有较高的失败率
    for i in range(300):
        task_id = f"task_{i:04d}"
        plan_id = "v2" if i % 4 == 0 else "v1"  # 25% 使用 v2
        # v2 有 50% 失败率，v1 全部成功
        if plan_id == "v2":
            state = "FAILED" if i % 2 == 0 else "COMPLETED"
        else:
            state = "COMPLETED"
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id=plan_id,
            current_plan_path_type="normal",
            cost_summary={"total": 0.3},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    kpi_collector = PolicyKPICollector(trace_store)
    rollback_manager = RollbackManager(
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    rollout_manager = RolloutManager(
        trace_store=trace_store,
        kpi_collector=kpi_collector,
        rollback_manager=rollback_manager,
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    # 手动设置状态为 partial
    state = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "stage": "partial",
        "traffic_split": {"v1": 0.75, "v2": 0.25},
        "started_at": datetime.now().isoformat(),
        "last_checked_at": datetime.now().isoformat(),
        "kpi_window": {"n_runs": 200, "lookback_minutes": 60},
        "thresholds": {
            "min_success_uplift": 0.00,
            "max_cost_increase": 0.05,
            "max_failure_rate": 0.15  # v2 的 50% 失败率会触发回滚
        }
    }
    rollout_manager.save_state(state)
    
    # 尝试推进（应该触发回滚）
    result = rollout_manager.advance_stage()
    
    # 应该失败并触发回滚
    assert result["success"] is False
    assert result["reason"] == "kpi_gate_failed"
    assert result["rollback_triggered"] is True
    
    # 验证状态已回滚
    new_state = rollout_manager.load_state()
    assert new_state["stage"] == "rollback"
    assert new_state["traffic_split"]["v1"] == 1.0
    
    print("✅ KPI 不达标触发 rollback 测试通过")


def test_policy_router_stable_hash(tmp_path, monkeypatch):
    """测试 PolicyRouter stable hash 功能"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    rollouts_dir.mkdir(parents=True)
    
    # 创建 rollout state
    state = {
        "active_policy": "v1",
        "candidate_policy": "v2",
        "stage": "canary",
        "traffic_split": {"v1": 0.95, "v2": 0.05}
    }
    state_path = rollouts_dir / "rollout_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    
    policy_router = PolicyRouter(rollout_state_path=str(state_path))
    
    # 测试同一 task_id 总是返回相同结果
    task_id = "test_task_123"
    results = set()
    for _ in range(100):
        result = policy_router.pick_policy({"task_id": task_id})
        results.add(result)
    
    # 应该只有一个结果（stable hash）
    assert len(results) == 1
    
    # 测试不同 task_id 会分配到不同 policy（统计上）
    v1_count = 0
    v2_count = 0
    for i in range(1000):
        result = policy_router.pick_policy({"task_id": f"task_{i}"})
        if result == "v1":
            v1_count += 1
        else:
            v2_count += 1
    
    # 应该大约 95% v1, 5% v2（允许一定误差）
    v2_ratio = v2_count / 1000
    assert 0.02 <= v2_ratio <= 0.10  # 2% - 10% 范围内
    
    print(f"✅ PolicyRouter stable hash 测试通过 (v2_ratio: {v2_ratio:.2%})")


def test_rollback_manager_should_rollback(tmp_path, monkeypatch):
    """测试 RollbackManager.should_rollback 逻辑"""
    monkeypatch.chdir(tmp_path)
    
    rollback_manager = RollbackManager()
    
    # 场景 1: failure_rate 超过阈值
    kpis_high_failure = {
        "v1": {"success_rate": 0.95, "failure_rate": 0.05, "avg_cost": 0.3},
        "v2": {"success_rate": 0.80, "failure_rate": 0.20, "avg_cost": 0.25}  # 20% > 15%
    }
    thresholds = {"max_failure_rate": 0.15, "max_cost_increase": 0.05}
    
    assert rollback_manager.should_rollback(kpis_high_failure, thresholds, "v1", "v2") is True
    
    # 场景 2: success_rate 显著下降
    kpis_low_success = {
        "v1": {"success_rate": 0.95, "failure_rate": 0.05, "avg_cost": 0.3},
        "v2": {"success_rate": 0.85, "failure_rate": 0.10, "avg_cost": 0.25}  # 下降 10%
    }
    
    assert rollback_manager.should_rollback(kpis_low_success, thresholds, "v1", "v2") is True
    
    # 场景 3: 正常情况，不需要回滚
    kpis_normal = {
        "v1": {"success_rate": 0.90, "failure_rate": 0.10, "avg_cost": 0.3},
        "v2": {"success_rate": 0.92, "failure_rate": 0.08, "avg_cost": 0.28}  # 更好
    }
    
    assert rollback_manager.should_rollback(kpis_normal, thresholds, "v1", "v2") is False
    
    print("✅ RollbackManager.should_rollback 测试通过")


def test_full_rollout_cycle(tmp_path, monkeypatch):
    """测试完整的 rollout 周期: canary -> partial -> full"""
    monkeypatch.chdir(tmp_path)
    
    # 创建目录
    trace_dir = tmp_path / "artifacts" / "trace_store"
    rollouts_dir = tmp_path / "artifacts" / "rollouts"
    trace_dir.mkdir(parents=True)
    rollouts_dir.mkdir(parents=True)
    
    trace_store = TraceStore(base_dir=str(trace_dir))
    
    # 创建 mock 数据，v2 表现更好
    for i in range(500):
        task_id = f"task_{i:04d}"
        # 随机分配 policy
        plan_id = "v2" if i % 3 == 0 else "v1"
        state = "COMPLETED"  # 全部成功
        
        summary = TraceSummary(
            task_id=task_id,
            state=state,
            current_plan_id=plan_id,
            current_plan_path_type="normal",
            cost_summary={"total": 0.25 if plan_id == "v2" else 0.30},  # v2 成本更低
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        trace_store.save_summary(summary)
    
    kpi_collector = PolicyKPICollector(trace_store)
    
    rollout_manager = RolloutManager(
        trace_store=trace_store,
        kpi_collector=kpi_collector,
        state_path=str(rollouts_dir / "rollout_state.json"),
        audit_log_path=str(rollouts_dir / "audit_log.jsonl")
    )
    
    # Step 1: 启动 canary
    result1 = rollout_manager.start_canary(active="v1", candidate="v2", canary_pct=0.05)
    assert result1["success"] is True
    assert result1["stage"] == "canary"
    
    # Step 2: 推进到 partial
    result2 = rollout_manager.advance_stage()
    assert result2["success"] is True
    assert result2["to_stage"] == "partial"
    
    # Step 3: 推进到 full
    result3 = rollout_manager.advance_stage()
    assert result3["success"] is True
    assert result3["to_stage"] == "full"
    assert result3["active_policy"] == "v2"
    
    # 验证最终状态
    final_state = rollout_manager.load_state()
    assert final_state["stage"] == "full"
    assert final_state["active_policy"] == "v2"
    assert final_state["previous_policy"] == "v1"
    
    # 验证审计日志
    audit_log_path = rollouts_dir / "audit_log.jsonl"
    assert audit_log_path.exists()
    
    with open(audit_log_path, "r", encoding="utf-8") as f:
        audit_entries = [json.loads(line) for line in f]
    
    # 应该有 3 条审计日志
    assert len(audit_entries) >= 3
    actions = [e["action"] for e in audit_entries]
    assert "start_canary" in actions
    assert "advance_stage" in actions
    
    print("✅ 完整 rollout 周期测试通过")



