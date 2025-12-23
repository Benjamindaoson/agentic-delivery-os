"""
Policy Router: 策略路由器
支持灰度流量分配，使用 stable hashing 确保同一 user/project/run_id 映射稳定
"""
import os
import json
import hashlib
from typing import Dict, Any, Optional


class PolicyRouter:
    """
    Policy Router：根据 traffic_split 返回应使用的 policy_id。
    
    使用 stable hashing（sha256）确保同一 user/project/run_id 映射稳定。
    """
    
    def __init__(
        self,
        rollout_state_path: str = "artifacts/rollouts/rollout_state.json"
    ):
        """
        初始化 Policy Router。
        
        Args:
            rollout_state_path: rollout 状态文件路径
        """
        self.rollout_state_path = rollout_state_path
    
    def pick_policy(self, run_context: Dict[str, Any]) -> str:
        """
        根据 traffic_split 返回应使用的 policy_id。
        
        Args:
            run_context: 运行上下文，必须包含至少一个可用于哈希的字段
                        （优先级：task_id > run_id > project_id + user_id > random）
                        
        Returns:
            str: policy_id
        """
        # 加载 rollout state
        rollout_state = self._load_rollout_state()
        
        if not rollout_state:
            # 无 rollout state -> 返回默认 active policy
            return self._resolve_default_active()
        
        stage = rollout_state.get("stage", "idle")
        
        if stage == "idle":
            return rollout_state.get("active_policy", self._resolve_default_active())
        
        if stage == "rollback":
            # 回滚阶段，100% 使用 active
            return rollout_state.get("active_policy", self._resolve_default_active())
        
        if stage == "full":
            # 全量发布完成，candidate 已成为 active
            return rollout_state.get("active_policy", self._resolve_default_active())
        
        # canary / partial 阶段，按 traffic_split 分流
        traffic_split = rollout_state.get("traffic_split", {})
        active_policy = rollout_state.get("active_policy")
        candidate_policy = rollout_state.get("candidate_policy")
        
        if not active_policy or not candidate_policy:
            return self._resolve_default_active()
        
        # 计算 stable hash
        hash_input = self._get_hash_input(run_context)
        hash_value = self._stable_hash(hash_input)
        
        # 按阈值切分
        candidate_ratio = traffic_split.get(candidate_policy, 0.0)
        
        if hash_value < candidate_ratio:
            return candidate_policy
        else:
            return active_policy
    
    def _load_rollout_state(self) -> Optional[Dict[str, Any]]:
        """加载 rollout 状态"""
        if not os.path.exists(self.rollout_state_path):
            return None
        
        try:
            with open(self.rollout_state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _resolve_default_active(self) -> str:
        """解析默认 active policy"""
        from runtime.agent_registry.version_resolver import resolve_active_policy
        
        try:
            policy = resolve_active_policy()
            return policy.get("policy_version", "v1")
        except Exception:
            return "v1"
    
    def _get_hash_input(self, run_context: Dict[str, Any]) -> str:
        """获取用于哈希的输入字符串"""
        # 优先级：task_id > run_id > project_id + user_id
        if "task_id" in run_context:
            return str(run_context["task_id"])
        
        if "run_id" in run_context:
            return str(run_context["run_id"])
        
        if "project_id" in run_context and "user_id" in run_context:
            return f"{run_context['project_id']}:{run_context['user_id']}"
        
        if "project_id" in run_context:
            return str(run_context["project_id"])
        
        # 如果没有可用字段，使用随机（但这会导致不稳定）
        import uuid
        return str(uuid.uuid4())
    
    def _stable_hash(self, input_str: str) -> float:
        """
        计算 stable hash，返回 [0, 1) 范围内的浮点数。
        
        Args:
            input_str: 输入字符串
            
        Returns:
            float: [0, 1) 范围内的哈希值
        """
        hash_bytes = hashlib.sha256(input_str.encode("utf-8")).digest()
        # 使用前 8 字节作为整数
        hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
        # 归一化到 [0, 1)
        return hash_int / (2 ** 64)
    
    def get_current_stage(self) -> str:
        """获取当前 rollout 阶段"""
        rollout_state = self._load_rollout_state()
        if not rollout_state:
            return "idle"
        return rollout_state.get("stage", "idle")
    
    def get_traffic_split(self) -> Dict[str, float]:
        """获取当前流量分配"""
        rollout_state = self._load_rollout_state()
        if not rollout_state:
            return {}
        return rollout_state.get("traffic_split", {})



