"""
Tests for Cognitive UI Data Source
Ensures data source doesn't crash on missing files
"""
import pytest
import os
import json
import tempfile
import shutil
from runtime.cognitive_ui.data_source import ArtifactDataSource


@pytest.fixture
def temp_artifacts_dir():
    """Create a temporary artifacts directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def data_source_with_empty_artifacts(temp_artifacts_dir):
    """Data source with empty artifacts directory"""
    return ArtifactDataSource(artifacts_root=temp_artifacts_dir)


@pytest.fixture
def data_source_with_sample_task(temp_artifacts_dir):
    """Data source with a sample task"""
    # Create rag_project structure
    task_id = "test_task_001"
    task_dir = os.path.join(temp_artifacts_dir, "rag_project", task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # Create delivery_manifest.json
    manifest = {
        "task_id": task_id,
        "created_at": "2024-01-01T00:00:00",
        "failed": False,
        "executed_agents": ["Product", "Data", "Execution"],
        "spec": {"goal": "test goal"}
    }
    with open(os.path.join(task_dir, "delivery_manifest.json"), "w") as f:
        json.dump(manifest, f)
    
    # Create system_trace.json
    trace = {
        "task_id": task_id,
        "agent_executions": [
            {
                "agent": "Product",
                "timestamp": "2024-01-01T00:00:01",
                "status": "success",
                "output": {"decision": "proceed"}
            }
        ],
        "governance_decisions": [
            {
                "checkpoint": "after_Product",
                "execution_mode": "normal",
                "timestamp": "2024-01-01T00:00:02"
            }
        ]
    }
    with open(os.path.join(task_dir, "system_trace.json"), "w") as f:
        json.dump(trace, f)
    
    # Create cost_report.json
    cost_report = [
        {"provider": "qwen", "estimated_cost": 0.05},
        {"provider": "qwen", "estimated_cost": 0.03}
    ]
    with open(os.path.join(task_dir, "cost_report.json"), "w") as f:
        json.dump(cost_report, f)
    
    return ArtifactDataSource(artifacts_root=temp_artifacts_dir), task_id


def test_list_tasks_empty(data_source_with_empty_artifacts):
    """Test list_tasks returns empty list when no tasks exist"""
    tasks = data_source_with_empty_artifacts.list_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 0


def test_list_tasks_with_tasks(data_source_with_sample_task):
    """Test list_tasks returns task IDs"""
    data_source, task_id = data_source_with_sample_task
    tasks = data_source.list_tasks()
    assert isinstance(tasks, list)
    assert task_id in tasks


def test_load_task_summary_missing(data_source_with_empty_artifacts):
    """Test load_task_summary returns empty structure for missing task"""
    summary = data_source_with_empty_artifacts.load_task_summary("nonexistent_task")
    
    assert isinstance(summary, dict)
    assert summary["task_id"] == "nonexistent_task"
    assert summary["status"] == "unknown"
    assert isinstance(summary["spec"], dict)
    assert isinstance(summary["agents_executed"], list)


def test_load_task_summary_exists(data_source_with_sample_task):
    """Test load_task_summary returns data for existing task"""
    data_source, task_id = data_source_with_sample_task
    summary = data_source.load_task_summary(task_id)
    
    assert isinstance(summary, dict)
    assert summary["task_id"] == task_id
    assert summary["status"] == "completed"
    assert "Product" in summary["agents_executed"]


def test_load_timeline_events_missing(data_source_with_empty_artifacts):
    """Test load_timeline_events returns empty list for missing task"""
    events = data_source_with_empty_artifacts.load_timeline_events("nonexistent_task")
    
    assert isinstance(events, list)
    assert len(events) == 0


def test_load_timeline_events_exists(data_source_with_sample_task):
    """Test load_timeline_events returns events for existing task"""
    data_source, task_id = data_source_with_sample_task
    events = data_source.load_timeline_events(task_id)
    
    assert isinstance(events, list)
    assert len(events) > 0
    
    # Check event structure
    for event in events:
        assert "timestamp" in event
        assert "type" in event


def test_load_cost_missing(data_source_with_empty_artifacts):
    """Test load_cost returns empty structure for missing task"""
    cost_info = data_source_with_empty_artifacts.load_cost("nonexistent_task")
    
    assert isinstance(cost_info, dict)
    assert cost_info["total_cost"] == 0.0
    assert isinstance(cost_info["cost_breakdown"], dict)


def test_load_cost_exists(data_source_with_sample_task):
    """Test load_cost returns data for existing task"""
    data_source, task_id = data_source_with_sample_task
    cost_info = data_source.load_cost(task_id)
    
    assert isinstance(cost_info, dict)
    assert cost_info["total_cost"] > 0.0
    assert isinstance(cost_info["cost_breakdown"], dict)


def test_load_governance_missing(data_source_with_empty_artifacts):
    """Test load_governance returns empty structure for missing task"""
    gov_info = data_source_with_empty_artifacts.load_governance("nonexistent_task")
    
    assert isinstance(gov_info, dict)
    assert isinstance(gov_info["decisions"], list)
    assert gov_info["degraded"] is False


def test_load_governance_exists(data_source_with_sample_task):
    """Test load_governance returns data for existing task"""
    data_source, task_id = data_source_with_sample_task
    gov_info = data_source.load_governance(task_id)
    
    assert isinstance(gov_info, dict)
    assert isinstance(gov_info["decisions"], list)
    assert len(gov_info["decisions"]) > 0


def test_load_plan_or_dag_missing(data_source_with_empty_artifacts):
    """Test load_plan_or_dag returns None for missing task"""
    plan_info = data_source_with_empty_artifacts.load_plan_or_dag("nonexistent_task")
    
    assert plan_info is None


def test_diff_tasks_stable_structure(data_source_with_sample_task):
    """Test diff_tasks returns stable structure"""
    data_source, task_id = data_source_with_sample_task
    
    # Diff same task (should not crash)
    diff = data_source.diff_tasks(task_id, task_id)
    
    assert isinstance(diff, dict)
    assert "task_a" in diff
    assert "task_b" in diff
    assert "cost_diff" in diff
    assert "decision_diff" in diff
    assert "artifact_diff" in diff
    
    # Check cost_diff structure
    cost_diff = diff["cost_diff"]
    assert "total_cost_a" in cost_diff
    assert "total_cost_b" in cost_diff
    assert "delta" in cost_diff
    
    # Check decision_diff structure
    decision_diff = diff["decision_diff"]
    assert "degraded_a" in decision_diff
    assert "degraded_b" in decision_diff
    
    # Check artifact_diff structure
    artifact_diff = diff["artifact_diff"]
    assert "only_in_a" in artifact_diff
    assert "only_in_b" in artifact_diff
    assert "in_both" in artifact_diff


def test_diff_tasks_missing_tasks(data_source_with_empty_artifacts):
    """Test diff_tasks handles missing tasks gracefully"""
    diff = data_source_with_empty_artifacts.diff_tasks("task_a", "task_b")
    
    assert isinstance(diff, dict)
    assert diff["task_a"] == "task_a"
    assert diff["task_b"] == "task_b"
    
    # Should have structure even with missing tasks
    assert "cost_diff" in diff
    assert "decision_diff" in diff
    assert "artifact_diff" in diff


def test_data_source_initialization():
    """Test data source initialization with various paths"""
    # Default path
    ds1 = ArtifactDataSource()
    assert ds1.artifacts_root == "artifacts"
    
    # Custom path
    ds2 = ArtifactDataSource(artifacts_root="/custom/path")
    assert ds2.artifacts_root == "/custom/path"


def test_data_source_no_crash_on_corrupted_json(temp_artifacts_dir):
    """Test data source doesn't crash on corrupted JSON files"""
    # Create task with corrupted JSON
    task_id = "corrupted_task"
    task_dir = os.path.join(temp_artifacts_dir, "rag_project", task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # Write corrupted JSON
    with open(os.path.join(task_dir, "delivery_manifest.json"), "w") as f:
        f.write("{ invalid json }")
    
    data_source = ArtifactDataSource(artifacts_root=temp_artifacts_dir)
    
    # Should not crash, just return empty/default data
    summary = data_source.load_task_summary(task_id)
    assert isinstance(summary, dict)
    assert summary["task_id"] == task_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

