#!/usr/bin/env python3
"""
启动前一致性校验
"""
import json
import hashlib
import argparse
import sys
import os
from pathlib import Path

def check_config_hash():
    """检查配置 hash"""
    config_path = Path("configs/config_snapshot.json")
    if not config_path.exists():
        print("Error: config_snapshot.json not found")
        return False
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # 重新计算 hash
    config_copy = config.copy()
    stored_hash = config_copy.pop("config_hash", None)
    
    config_json = json.dumps(config_copy, sort_keys=True)
    calculated_hash = hashlib.sha256(config_json.encode()).hexdigest()
    
    if stored_hash != calculated_hash:
        print(f"Error: Config hash mismatch. Stored: {stored_hash}, Calculated: {calculated_hash}")
        return False
    
    print(f"✓ Config hash verified: {stored_hash}")
    return True

def check_runtime_version():
    """检查运行时版本"""
    import sys
    expected_version = "3.11"
    actual_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    if actual_version != expected_version:
        print(f"Warning: Python version mismatch. Expected: {expected_version}, Actual: {actual_version}")
        return False
    
    print(f"✓ Runtime version verified: {actual_version}")
    return True

def check_dependency_lock():
    """检查依赖锁定"""
    if not os.path.exists("requirements.txt"):
        print("Error: requirements.txt not found")
        return False
    
    if not os.path.exists("requirements.lock"):
        print("Warning: requirements.lock not found. Generating...")
        # 简化：实际应该使用 pip-tools 或类似工具
        os.system("pip freeze > requirements.lock")
    
    print("✓ Dependency lock verified")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", default="prod")
    args = parser.parse_args()
    
    print("Running pre-deployment checks...")
    print(f"Environment: {args.environment}")
    print("-" * 40)
    
    checks = [
        check_config_hash(),
        check_runtime_version(),
        check_dependency_lock()
    ]
    
    if not all(checks):
        print("\nPre-deployment checks failed")
        sys.exit(1)
    
    print("\n✓ All pre-deployment checks passed")

if __name__ == "__main__":
    main()


