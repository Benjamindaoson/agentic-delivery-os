#!/usr/bin/env python3
"""
生成配置快照
"""
import json
import hashlib
import argparse
import os
from datetime import datetime
from pathlib import Path

def generate_config_snapshot(environment: str):
    """生成配置快照"""
    config_dir = Path("configs")
    config_dir.mkdir(exist_ok=True)
    
    # 收集配置
    config = {
        "version": "1.0",
        "environment": environment,
        "timestamp": datetime.now().isoformat(),
        "runtime_version": "python3.11",
        "dependencies": _load_dependencies(),
        "system_config": _load_system_config(),
        "deployment_config": _load_deployment_config(environment)
    }
    
    # 计算 hash
    config_json = json.dumps(config, sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    config["config_hash"] = config_hash
    
    # 保存快照
    snapshot_path = config_dir / f"config_snapshot_{environment}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # 保存当前快照（用于回滚）
    current_snapshot_path = config_dir / "config_snapshot.json"
    with open(current_snapshot_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"Config snapshot generated: {snapshot_path}")
    print(f"Config hash: {config_hash}")
    return config_hash

def _load_dependencies():
    """加载依赖版本"""
    deps = {}
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "==" in line:
                        pkg, version = line.split("==")
                        deps[pkg.strip()] = version.strip()
    return deps

def _load_system_config():
    """加载系统配置"""
    config_path = Path("configs/system.yaml")
    if config_path.exists():
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def _load_deployment_config(environment: str):
    """加载部署配置"""
    return {
        "environment": environment,
        "docker_compose_version": "3.8",
        "ports": {
            "backend": 8000,
            "frontend": 3000,
            "redis": 6379
        }
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", default="prod", choices=["dev", "staging", "prod"])
    args = parser.parse_args()
    
    generate_config_snapshot(args.environment)


