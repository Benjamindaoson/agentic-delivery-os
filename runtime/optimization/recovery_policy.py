"""
Failure Taxonomy + Recovery Policy: 失败分类与恢复策略映射
统一失败类型 + 恢复策略映射（确定性规则）
最短修复路径：避免全链路重跑
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class FailureType(str, Enum):
    """失败类型"""
    DATA_ISSUE = "data_issue"
    EXECUTION_ISSUE = "execution_issue"
    COST_ISSUE = "cost_issue"
    SPEC_ISSUE = "spec_issue"
    TOOL_ISSUE = "tool_issue"

class RecoveryPolicy(str, Enum):
    """恢复策略"""
    ASK_USER = "ask_user"
    DEGRADE_PARSING = "degrade_parsing"
    MINIMAL_PATH = "minimal_path"
    SANDBOX_RETRY = "sandbox_retry"
    PARTIAL_PATCH = "partial_patch"
    ROLLBACK = "rollback"
    BUDGET_REALLOCATE = "budget_reallocate"
    PAUSED_REQUEST_CLARIFICATION = "paused_request_clarification"
    TOOL_ALLOWLIST_TIGHTEN = "tool_allowlist_tighten"
    RETRY_ONCE = "retry_once"
    DEGRADE = "degrade"

@dataclass
class RecoveryPlan:
    """恢复计划"""
    failure_type: FailureType
    recovery_policy: RecoveryPolicy
    affected_nodes: List[str]
    recovery_evidence: Dict[str, Any]

class RecoveryPolicyMapper:
    """恢复策略映射器（确定性规则）"""
    
    def __init__(self):
        self.version = "1.0"
        # 失败类型 → 恢复策略映射（确定性规则）
        self.mapping = {
            FailureType.DATA_ISSUE: [
                RecoveryPolicy.ASK_USER,
                RecoveryPolicy.DEGRADE_PARSING,
                RecoveryPolicy.MINIMAL_PATH
            ],
            FailureType.EXECUTION_ISSUE: [
                RecoveryPolicy.SANDBOX_RETRY,
                RecoveryPolicy.PARTIAL_PATCH,
                RecoveryPolicy.ROLLBACK
            ],
            FailureType.COST_ISSUE: [
                RecoveryPolicy.BUDGET_REALLOCATE,
                RecoveryPolicy.MINIMAL_PATH
            ],
            FailureType.SPEC_ISSUE: [
                RecoveryPolicy.PAUSED_REQUEST_CLARIFICATION
            ],
            FailureType.TOOL_ISSUE: [
                RecoveryPolicy.TOOL_ALLOWLIST_TIGHTEN,
                RecoveryPolicy.RETRY_ONCE,
                RecoveryPolicy.DEGRADE
            ]
        }
    
    def map_failure_to_recovery(
        self,
        failure_type: str,
        affected_nodes: List[str],
        context: Dict[str, Any]
    ) -> RecoveryPlan:
        """
        映射失败类型到恢复策略
        
        Args:
            failure_type: 失败类型
            affected_nodes: 受影响节点
            context: 上下文
        
        Returns:
            RecoveryPlan: 恢复计划
        """
        # 转换为枚举
        try:
            ft_enum = FailureType(failure_type)
        except ValueError:
            ft_enum = FailureType.EXECUTION_ISSUE  # 默认
        
        # 选择恢复策略（第一个）
        policies = self.mapping.get(ft_enum, [RecoveryPolicy.ASK_USER])
        selected_policy = policies[0]
        
        # 生成证据
        recovery_evidence = {
            "recovery_policy_mapper_version": self.version,
            "failure_type": failure_type,
            "selected_policy": selected_policy.value,
            "available_policies": [p.value for p in policies],
            "affected_nodes": affected_nodes,
            "context_summary": {
                "budget_remaining": context.get("budget_remaining", 0),
                "retry_count": context.get("retry_count", 0)
            }
        }
        
        return RecoveryPlan(
            failure_type=ft_enum,
            recovery_policy=selected_policy,
            affected_nodes=affected_nodes,
            recovery_evidence=recovery_evidence
        )


