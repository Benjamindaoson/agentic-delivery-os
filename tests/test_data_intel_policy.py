"""
Unit tests for Data Intelligence Agent policy resolution.
"""

import pytest
from runtime.data_intel import policy_resolver


def _mock_strategy_entry():
    return {
        "file_path": "file1.pdf",
        "strategies": [
            {"id": "s_low_cost", "cost_estimate": 0.2, "accuracy_band": "medium", "latency_class": "low"},
            {"id": "s_high_acc", "cost_estimate": 1.0, "accuracy_band": "high", "latency_class": "high"},
        ],
    }


def _mock_tradeoff_entry():
    return {
        "file_path": "file1.pdf",
        "tradeoffs": [
            {"tradeoff_type": "cost_accuracy", "label": "RESOLVABLE"},
        ],
    }


def test_policy_authorized_auto_resolve():
    res = policy_resolver.resolve(
        file_entry=_mock_strategy_entry(),
        tradeoff_entry=_mock_tradeoff_entry(),
        tenant_policy={
            "allowed_tradeoff_types": ["cost_accuracy"],
            "auto_resolution_priority": "cost_first",
        },
        tenant_context={"unattended_mode": True},
        system_constraints={},
    )
    assert res["status"] == policy_resolver.ResolutionStatus.AUTO_RESOLVED
    assert res["chosen_strategy_id"] == "s_low_cost"


def test_policy_violation():
    res = policy_resolver.resolve(
        file_entry=_mock_strategy_entry(),
        tradeoff_entry=_mock_tradeoff_entry(),
        tenant_policy={
            "allowed_tradeoff_types": [],  # not allowed
        },
        tenant_context={"unattended_mode": True},
        system_constraints={},
    )
    assert res["status"] == policy_resolver.ResolutionStatus.POLICY_VIOLATION


def test_unattended_no_policy():
    res = policy_resolver.resolve(
        file_entry=_mock_strategy_entry(),
        tradeoff_entry=_mock_tradeoff_entry(),
        tenant_policy=None,
        tenant_context={"unattended_mode": True},
        system_constraints={},
    )
    assert res["status"] == policy_resolver.ResolutionStatus.UNAUTHORIZED_TRADEOFF
