"""
Health Check endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
import json
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    }

@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """详细健康检查"""
    checks = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "checks": {}
    }
    
    # 检查 artifacts 目录
    artifacts_dir = "artifacts"
    checks["checks"]["artifacts_dir"] = {
        "status": "ok" if os.path.exists(artifacts_dir) else "error",
        "path": artifacts_dir
    }
    
    # 检查 config
    config_file = "configs/config_snapshot.json"
    checks["checks"]["config"] = {
        "status": "ok" if os.path.exists(config_file) else "error",
        "path": config_file
    }
    
    # 检查数据库连接（简化）
    checks["checks"]["database"] = {
        "status": "ok"  # 简化：实际应该检查数据库连接
    }
    
    # 检查 Redis 连接（简化）
    checks["checks"]["redis"] = {
        "status": "ok"  # 简化：实际应该检查 Redis 连接
    }
    
    # 如果有任何检查失败，返回 unhealthy
    if any(check["status"] == "error" for check in checks["checks"].values()):
        checks["status"] = "unhealthy"
        raise HTTPException(status_code=503, detail=checks)
    
    return checks

@router.get("/health/metrics")
async def health_metrics() -> Dict[str, Any]:
    """健康指标"""
    # 从 observability 模块获取指标
    from runtime.platform.observability import Observability
    
    observability = Observability()
    
    # 简化：实际应该从实际运行数据中获取
    return {
        "success_rate": 0.95,  # 占位
        "failure_rate": 0.05,  # 占位
        "cost_spike": False,  # 占位
        "abnormal_replay_length": False,  # 占位
        "timestamp": datetime.now().isoformat()
    }


