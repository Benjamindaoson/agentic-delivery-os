"""
Version resolver to check DAG compatibility.
Also handles policy version resolution and switching.
"""
import os
import json
from typing import List, Dict, Any, Optional
from runtime.agent_registry.agent_spec import AgentSpec
from runtime.extensions.policy_pack import load_policy_artifact

# Policy 存储目录（默认）
DEFAULT_POLICY_DIR = "artifacts/policies"
# Active policy 配置键（环境变量或配置文件）
ACTIVE_POLICY_ENV = "ACTIVE_POLICY_VERSION"
ACTIVE_POLICY_CONFIG_KEY = "active_policy_version"


def check_compatibility(agent_specs: List[AgentSpec]) -> bool:
    """
    Ensure no conflicting versions for same agent_id in one DAG.
    """
    seen = {}
    for spec in agent_specs:
        if spec.agent_id in seen and seen[spec.agent_id] != spec.agent_version:
            return False
        seen[spec.agent_id] = spec.agent_version
    return True


def resolve_active_policy(
    policy_dir: str = DEFAULT_POLICY_DIR,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    返回当前 active policy。
    支持通过配置 / 环境变量切换版本。
    
    Args:
        policy_dir: policy artifact 存储目录
        config: 可选的配置 dict（可以包含 active_policy_version）
        
    Returns:
        policy artifact dict
        
    Raises:
        FileNotFoundError: 如果指定的 policy 文件不存在
    """
    # 优先级：环境变量 > config > 默认（最新版本）
    active_version = None
    
    # 1. 检查环境变量
    if ACTIVE_POLICY_ENV in os.environ:
        active_version = os.environ[ACTIVE_POLICY_ENV]
    
    # 2. 检查 config
    if not active_version and config:
        active_version = config.get(ACTIVE_POLICY_CONFIG_KEY)
    
    # 3. 如果没有指定版本，查找最新版本
    if not active_version:
        active_version = _find_latest_policy_version(policy_dir)
    
    # 4. 如果还是没有，返回默认 policy
    if not active_version:
        return _default_policy()
    
    # 5. 加载指定的 policy
    policy_path = os.path.join(policy_dir, f"policy_{active_version}.json")
    if not os.path.exists(policy_path):
        # 如果指定的 policy 不存在，尝试回退到上一个版本
        fallback_version = _find_previous_policy_version(policy_dir, active_version)
        if fallback_version:
            policy_path = os.path.join(policy_dir, f"policy_{fallback_version}.json")
        else:
            # 如果连 fallback 都没有，返回默认 policy
            return _default_policy()
    
    try:
        return load_policy_artifact(policy_path)
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果加载失败，返回默认 policy
        return _default_policy()


def _find_latest_policy_version(policy_dir: str) -> Optional[str]:
    """查找最新的 policy 版本"""
    if not os.path.exists(policy_dir):
        return None
    
    policy_files = [
        f for f in os.listdir(policy_dir)
        if f.startswith("policy_") and f.endswith(".json")
    ]
    
    if not policy_files:
        return None
    
    # 提取版本号并排序
    versions = []
    for filename in policy_files:
        # 格式：policy_v1.json -> v1
        version_str = filename[7:-5]  # 移除 "policy_" 前缀和 ".json" 后缀
        try:
            # 提取数字部分
            version_num = _extract_version_number(version_str)
            versions.append((version_num, version_str))
        except (ValueError, AttributeError):
            continue
    
    if not versions:
        return None
    
    # 返回最新版本
    versions.sort(key=lambda x: x[0], reverse=True)
    return versions[0][1]


def _find_previous_policy_version(policy_dir: str, current_version: str) -> Optional[str]:
    """查找上一个 policy 版本（用于回滚）"""
    if not os.path.exists(policy_dir):
        return None
    
    try:
        current_num = _extract_version_number(current_version)
    except (ValueError, AttributeError):
        return None
    
    policy_files = [
        f for f in os.listdir(policy_dir)
        if f.startswith("policy_") and f.endswith(".json")
    ]
    
    # 找出所有小于当前版本的版本
    candidates = []
    for filename in policy_files:
        version_str = filename[7:-5]
        try:
            version_num = _extract_version_number(version_str)
            if version_num < current_num:
                candidates.append((version_num, version_str))
        except (ValueError, AttributeError):
            continue
    
    if not candidates:
        return None
    
    # 返回最大的候选版本（最接近当前版本的旧版本）
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _extract_version_number(version_str: str) -> int:
    """从版本字符串提取数字（例如 "v3" -> 3）"""
    try:
        if version_str.startswith("v"):
            return int(version_str[1:])
        return int(version_str)
    except (ValueError, AttributeError):
        return 1


def _default_policy() -> Dict[str, Any]:
    """返回默认 policy（当没有找到任何 policy 时）"""
    return {
        "policy_version": "v1",
        "plan_selection_rules": {
            "prefer_plan": "normal",
            "fallback_order": ["normal", "degraded", "minimal"]
        },
        "thresholds": {
            "max_cost_usd": 0.5,
            "max_latency_ms": 3000,
            "failure_rate_tolerance": 0.1
        },
        "metadata": {
            "generated_at": 0,
            "source_runs": 0,
            "note": "default_policy"
        }
    }

