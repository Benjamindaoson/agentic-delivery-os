"""
Security: RBAC / 脱敏 / 审计
目标：商业化前置能力
"""
import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

class Role(str, Enum):
    """角色"""
    OWNER = "owner"
    VIEWER = "viewer"
    OPERATOR = "operator"

@dataclass
class AuditLog:
    """审计日志"""
    timestamp: str
    user_id: str
    role: Role
    action: str
    resource: str
    result: str

class SecurityEngine:
    """安全引擎"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "sensitive_fields": [
                "prompt",
                "raw_prompt",
                "api_key",
                "secret",
                "password",
                "token"
            ],
            "hash_salt": "default_salt_change_in_production"
        }
        self.version = "1.0"
        self.audit_logs: List[AuditLog] = []
    
    def check_permission(self, user_id: str, role: Role, action: str, resource: str) -> bool:
        """检查权限（确定性规则）"""
        # 规则：OWNER 可读写，VIEWER 只读，OPERATOR 可执行
        if role == Role.OWNER:
            return True
        elif role == Role.VIEWER:
            return action in ["read", "view"]
        elif role == Role.OPERATOR:
            return action in ["read", "view", "execute", "resume"]
        return False
    
    def sanitize_trace(self, trace_data: Dict[str, Any], role: Role) -> Dict[str, Any]:
        """脱敏 trace（确定性规则）"""
        sanitized = json.loads(json.dumps(trace_data))  # 深拷贝
        
        # 规则：VIEWER 和 OPERATOR 需要脱敏
        if role in [Role.VIEWER, Role.OPERATOR]:
            self._sanitize_dict(sanitized, self.config["sensitive_fields"])
        
        return sanitized
    
    def _sanitize_dict(self, data: Dict[str, Any], sensitive_fields: List[str]):
        """递归脱敏字典"""
        for key, value in data.items():
            if isinstance(value, dict):
                self._sanitize_dict(value, sensitive_fields)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._sanitize_dict(item, sensitive_fields)
            elif key.lower() in [f.lower() for f in sensitive_fields]:
                # 脱敏：hash 或替换
                if isinstance(value, str):
                    data[key] = f"[REDACTED:{self._hash_value(value)}]"
                else:
                    data[key] = "[REDACTED]"
    
    def _hash_value(self, value: str) -> str:
        """Hash 值（用于脱敏标识）"""
        return hashlib.sha256(
            (value + self.config["hash_salt"]).encode()
        ).hexdigest()[:8]
    
    def log_audit(self, user_id: str, role: Role, action: str, resource: str, result: str):
        """记录审计日志"""
        log = AuditLog(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            role=role,
            action=action,
            resource=resource,
            result=result
        )
        self.audit_logs.append(log)
    
    def get_audit_logs(self, user_id: Optional[str] = None, resource: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取审计日志"""
        logs = self.audit_logs
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if resource:
            logs = [l for l in logs if l.resource == resource]
        return [{
            "timestamp": l.timestamp,
            "user_id": l.user_id,
            "role": l.role.value,
            "action": l.action,
            "resource": l.resource,
            "result": l.result
        } for l in logs]


