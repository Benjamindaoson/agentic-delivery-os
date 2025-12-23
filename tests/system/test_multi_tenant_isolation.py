"""
System-level Tests: Multi-Tenant Isolation
测试租户隔离、预算控制、学习隔离
"""
import pytest
import os
import json
from runtime.tenancy.tenant_budget_controller import (
    TenantBudgetController,
    BudgetStatus,
    get_tenant_budget_controller
)
from runtime.tenancy.learning_profile import (
    TenantLearningProfile,
    LearningIntensity,
    get_tenant_learning_profile
)
from runtime.tenancy.tenant import TenantManager, BudgetProfile


def test_tenant_budget_initialization():
    """测试租户预算初始化"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    # Register first task
    result = controller.register_task_start(
        tenant_id="tenant_test_1",
        task_id="task_1",
        run_id="run_1",
        estimated_cost=10.0
    )
    
    assert result["allowed"] is True
    assert result["budget_remaining"] > 0
    
    # Get usage
    usage = controller.get_budget_usage("tenant_test_1")
    assert usage.tenant_id == "tenant_test_1"
    assert usage.concurrent_runs == 1


def test_tenant_budget_limit_enforcement():
    """测试租户预算限制执行"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    # Manually set a very low budget
    usage = controller._get_usage("tenant_test_2")
    usage.budget_limit = 10.0
    controller._save_usage(usage)
    
    # Try to register task with high cost
    result = controller.register_task_start(
        tenant_id="tenant_test_2",
        task_id="task_1",
        run_id="run_1",
        estimated_cost=50.0  # Exceeds budget
    )
    
    assert result["allowed"] is False
    assert "Budget limit exceeded" in result["reason"]


def test_tenant_budget_concurrent_limit():
    """测试租户并发限制"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    # Set max concurrent runs to 2
    usage = controller._get_usage("tenant_test_3")
    usage.max_concurrent_runs = 2
    controller._save_usage(usage)
    
    # Register 2 tasks (should succeed)
    for i in range(2):
        result = controller.register_task_start(
            tenant_id="tenant_test_3",
            task_id=f"task_{i}",
            run_id=f"run_{i}",
            estimated_cost=1.0
        )
        assert result["allowed"] is True
    
    # Try to register 3rd task (should fail)
    result = controller.register_task_start(
        tenant_id="tenant_test_3",
        task_id="task_3",
        run_id="run_3",
        estimated_cost=1.0
    )
    
    assert result["allowed"] is False
    assert "Concurrent runs limit exceeded" in result["reason"]


def test_tenant_budget_cost_tracking():
    """测试租户成本跟踪"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    tenant_id = "tenant_test_4"
    task_id = "task_1"
    
    # Start task
    controller.register_task_start(tenant_id, task_id, "run_1", estimated_cost=5.0)
    
    # Record cost increments
    controller.record_task_cost(tenant_id, task_id, 3.0, "llm")
    controller.record_task_cost(tenant_id, task_id, 2.0, "retrieval")
    controller.record_task_cost(tenant_id, task_id, 1.0, "storage")
    
    # Check usage
    usage = controller.get_budget_usage(tenant_id)
    assert usage.current_usage == 6.0
    assert usage.cost_by_category.get("llm", 0.0) == 3.0
    assert usage.cost_by_category.get("retrieval", 0.0) == 2.0
    assert usage.cost_by_category.get("storage", 0.0) == 1.0
    
    # End task
    controller.register_task_end(tenant_id, task_id, final_cost=6.0)
    
    # Check concurrent runs decreased
    usage = controller.get_budget_usage(tenant_id)
    assert usage.concurrent_runs == 0


def test_tenant_budget_status_calculation():
    """测试租户预算状态计算"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    tenant_id = "tenant_test_5"
    
    # Set budget and usage for different states
    usage = controller._get_usage(tenant_id)
    usage.budget_limit = 100.0
    
    # HEALTHY (<80%)
    usage.current_usage = 70.0
    usage.usage_rate = 0.7
    usage.status = controller._calculate_status(usage.usage_rate)
    assert usage.status == BudgetStatus.HEALTHY
    
    # WARNING (80-90%)
    usage.current_usage = 85.0
    usage.usage_rate = 0.85
    usage.status = controller._calculate_status(usage.usage_rate)
    assert usage.status == BudgetStatus.WARNING
    
    # CRITICAL (90-100%)
    usage.current_usage = 95.0
    usage.usage_rate = 0.95
    usage.status = controller._calculate_status(usage.usage_rate)
    assert usage.status == BudgetStatus.CRITICAL
    
    # EXCEEDED (>100%)
    usage.current_usage = 105.0
    usage.usage_rate = 1.05
    usage.status = controller._calculate_status(usage.usage_rate)
    assert usage.status == BudgetStatus.EXCEEDED


def test_tenant_learning_profile_initialization():
    """测试租户学习配置初始化"""
    profile_mgr = TenantLearningProfile(artifacts_dir="artifacts/test_tenants")
    
    # Get default profile
    profile = profile_mgr.get_profile("tenant_learn_1")
    
    assert profile.intensity == LearningIntensity.BALANCED
    assert 0 < profile.exploration_rate < 1
    assert profile.min_runs_for_learning > 0


def test_tenant_learning_profile_intensity_levels():
    """测试不同学习强度级别"""
    profile_mgr = TenantLearningProfile(artifacts_dir="artifacts/test_tenants")
    
    # CONSERVATIVE
    profile_mgr.set_profile("tenant_learn_2", LearningIntensity.CONSERVATIVE)
    profile = profile_mgr.get_profile("tenant_learn_2")
    assert profile.exploration_rate < 0.1
    assert profile.learning_budget_pct < 0.1
    
    # BALANCED
    profile_mgr.set_profile("tenant_learn_3", LearningIntensity.BALANCED)
    profile = profile_mgr.get_profile("tenant_learn_3")
    assert 0.1 <= profile.exploration_rate <= 0.2
    
    # AGGRESSIVE
    profile_mgr.set_profile("tenant_learn_4", LearningIntensity.AGGRESSIVE)
    profile = profile_mgr.get_profile("tenant_learn_4")
    assert profile.exploration_rate > 0.15
    assert profile.learning_budget_pct > 0.15


def test_tenant_learning_budget_linkage():
    """测试学习预算与租户预算联动"""
    profile_mgr = TenantLearningProfile(artifacts_dir="artifacts/test_tenants")
    
    tenant_id = "tenant_learn_5"
    total_budget = 1000.0
    
    # Set AGGRESSIVE profile
    profile_mgr.set_profile(tenant_id, LearningIntensity.AGGRESSIVE)
    
    # Calculate learning budget
    learning_budget = profile_mgr.calculate_learning_budget(tenant_id, total_budget)
    
    assert learning_budget > 0
    assert learning_budget <= total_budget * 0.3  # Max 30% for aggressive


def test_tenant_learning_dynamic_adjustment():
    """测试学习配置的动态调整"""
    profile_mgr = TenantLearningProfile(artifacts_dir="artifacts/test_tenants")
    
    tenant_id = "tenant_learn_6"
    
    # Set initial profile
    profile_mgr.set_profile(tenant_id, LearningIntensity.BALANCED)
    initial_profile = profile_mgr.get_profile(tenant_id)
    initial_exploration = initial_profile.exploration_rate
    
    # Adjust based on high budget utilization (>90%)
    adjusted_profile = profile_mgr.adjust_profile_by_budget(tenant_id, 0.95)
    
    # Should reduce exploration
    assert adjusted_profile.exploration_rate < initial_exploration
    assert adjusted_profile.enable_exploration is False


def test_tenant_isolation_no_cross_tenant_contamination():
    """测试租户之间不会相互污染"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    # Tenant A registers task and incurs cost
    controller.register_task_start("tenant_a", "task_a", "run_a", 5.0)
    controller.record_task_cost("tenant_a", "task_a", 10.0, "llm")
    
    # Tenant B registers task and incurs cost
    controller.register_task_start("tenant_b", "task_b", "run_b", 3.0)
    controller.record_task_cost("tenant_b", "task_b", 7.0, "llm")
    
    # Check isolation
    usage_a = controller.get_budget_usage("tenant_a")
    usage_b = controller.get_budget_usage("tenant_b")
    
    assert usage_a.current_usage == 10.0
    assert usage_b.current_usage == 7.0
    assert usage_a.concurrent_runs == 1
    assert usage_b.concurrent_runs == 1


def test_tenant_cost_report_generation():
    """测试租户成本报表生成"""
    controller = TenantBudgetController(artifacts_dir="artifacts/test_tenants")
    
    tenant_id = "tenant_report_1"
    
    # Register and complete some tasks
    for i in range(3):
        task_id = f"task_{i}"
        controller.register_task_start(tenant_id, task_id, f"run_{i}", 2.0)
        controller.record_task_cost(tenant_id, task_id, 5.0, "llm")
        controller.register_task_end(tenant_id, task_id, 5.0)
    
    # Generate report
    report = controller.generate_cost_report(tenant_id)
    
    assert report["tenant_id"] == tenant_id
    assert report["budget"]["used"] == 15.0
    assert len(report["top_cost_tasks"]) == 3


def test_tenant_manager_integration():
    """测试 TenantManager 集成"""
    manager = TenantManager(storage_path="artifacts/test_tenants")
    
    # Create tenant
    budget_profile = BudgetProfile(
        max_cost_per_day=100.0,
        max_cost_per_month=3000.0,
        max_concurrent_runs=5,
        max_agents=10,
        priority_level=5
    )
    
    tenant = manager.create_tenant(
        name="Test Tenant Integration",
        budget_profile=budget_profile,
        tenant_id="tenant_integration_1"
    )
    
    assert tenant.tenant_id == "tenant_integration_1"
    assert tenant.budget_profile.max_cost_per_day == 100.0
    
    # Get tenant
    retrieved = manager.get_tenant("tenant_integration_1")
    assert retrieved is not None
    assert retrieved.name == "Test Tenant Integration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

