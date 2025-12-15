"""
Multi-Tenant & Access Control
Tenant 隔离、API Key、Rate Limit、权限模型
"""
import os
import json
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

class TenantRole(str, Enum):
    """Tenant 角色"""
    OWNER = "owner"
    OPERATOR = "operator"
    VIEWER = "viewer"

@dataclass
class Tenant:
    """Tenant 定义"""
    tenant_id: str
    tenant_name: str
    created_at: str
    api_key: str
    api_key_hash: str
    rate_limit: int  # requests per minute
    quota: Dict[str, Any]  # task_count, token_usage, etc.
    roles: Dict[str, List[str]]  # {role: [user_ids]}
    metadata: Dict[str, Any]

@dataclass
class AccessLog:
    """访问审计日志"""
    log_id: str
    tenant_id: str
    user_id: Optional[str]
    api_key: str  # 已脱敏
    endpoint: str
    method: str
    timestamp: str
    status_code: int
    response_time_ms: float

class TenantManager:
    """Tenant 管理器"""
    
    def __init__(self, base_dir: str = "artifacts/tenants"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.tenants: Dict[str, Tenant] = {}
        self._load_tenants()
    
    def _load_tenants(self):
        """加载所有 tenants"""
        tenants_file = os.path.join(self.base_dir, "tenants.json")
        if os.path.exists(tenants_file):
            with open(tenants_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for tenant_data in data.get("tenants", []):
                    tenant = Tenant(**tenant_data)
                    self.tenants[tenant.tenant_id] = tenant
    
    def _save_tenants(self):
        """保存所有 tenants"""
        tenants_file = os.path.join(self.base_dir, "tenants.json")
        data = {
            "version": "1.0",
            "tenants": [asdict(tenant) for tenant in self.tenants.values()]
        }
        with open(tenants_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def create_tenant(
        self,
        tenant_name: str,
        rate_limit: int = 100,
        quota: Optional[Dict[str, Any]] = None
    ) -> Tenant:
        """创建新 tenant"""
        tenant_id = f"tenant_{secrets.token_urlsafe(16)}"
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            created_at=datetime.now().isoformat(),
            api_key=api_key,
            api_key_hash=api_key_hash,
            rate_limit=rate_limit,
            quota=quota or {
                "task_count": 1000,
                "token_usage": 1000000,
                "tool_calls": 10000
            },
            roles={
                TenantRole.OWNER.value: [],
                TenantRole.OPERATOR.value: [],
                TenantRole.VIEWER.value: []
            },
            metadata={}
        )
        
        self.tenants[tenant_id] = tenant
        self._save_tenants()
        
        # 创建 tenant 目录
        tenant_dir = os.path.join(self.base_dir, tenant_id)
        os.makedirs(tenant_dir, exist_ok=True)
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取 tenant"""
        return self.tenants.get(tenant_id)
    
    def get_tenant_by_api_key(self, api_key: str) -> Optional[Tenant]:
        """通过 API key 获取 tenant"""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        for tenant in self.tenants.values():
            if tenant.api_key_hash == api_key_hash:
                return tenant
        return None
    
    def verify_api_key(self, api_key: str) -> bool:
        """验证 API key"""
        return self.get_tenant_by_api_key(api_key) is not None
    
    def check_rate_limit(self, tenant_id: str) -> bool:
        """检查 rate limit"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        # 简化：实际应该使用 Redis 或类似工具
        # 这里仅做基本检查
        return True
    
    def check_quota(self, tenant_id: str, resource: str, amount: int) -> bool:
        """检查 quota"""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        current_usage = tenant.metadata.get("usage", {}).get(resource, 0)
        quota_limit = tenant.quota.get(resource, 0)
        
        return current_usage + amount <= quota_limit
    
    def log_access(self, access_log: AccessLog):
        """记录访问日志（不可被 tenant 修改）"""
        log_dir = os.path.join(self.base_dir, "access_logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"{access_log.tenant_id}_{datetime.now().strftime('%Y%m%d')}.jsonl")
        
        # 追加模式（只追加，不可修改）
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(access_log), ensure_ascii=False) + "\n")
    
    def ensure_tenant_isolation(self, tenant_id: str, resource_path: str) -> bool:
        """确保 tenant 隔离（tenant 之间不可读取彼此数据）"""
        # 检查路径是否属于该 tenant
        if not resource_path.startswith(f"artifacts/tenants/{tenant_id}"):
            return False
        
        # 检查路径是否包含其他 tenant
        parts = resource_path.split("/")
        if "tenants" in parts:
            tenant_index = parts.index("tenants")
            if tenant_index + 1 < len(parts):
                resource_tenant_id = parts[tenant_index + 1]
                if resource_tenant_id != tenant_id:
                    return False
        
        return True


