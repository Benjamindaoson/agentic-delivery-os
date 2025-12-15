"""
Metrics Registry Hasher: 计算 metrics_registry.json 的 hash
"""
import json
import hashlib

def calculate_metrics_registry_hash():
    """计算 metrics_registry.json 的 hash"""
    registry_path = "runtime/eval/metrics_registry.json"
    
    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)
    
    # 计算 hash
    registry_json = json.dumps(registry_data, sort_keys=True)
    registry_hash = hashlib.sha256(registry_json.encode()).hexdigest()
    
    # 保存 hash
    hash_path = "runtime/eval/metrics_registry.hash"
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(f"sha256:{registry_hash}")
    
    print(f"Metrics registry hash: sha256:{registry_hash}")
    return registry_hash

if __name__ == "__main__":
    calculate_metrics_registry_hash()


