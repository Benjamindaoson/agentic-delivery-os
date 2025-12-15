"""
System Matrix Hasher: 计算 system_matrix.json 的 hash
"""
import json
import hashlib

def calculate_system_matrix_hash():
    """计算 system_matrix.json 的 hash"""
    matrix_path = "runtime/eval/system_matrix.json"
    
    with open(matrix_path, "r", encoding="utf-8") as f:
        matrix_data = json.load(f)
    
    # 计算 hash
    matrix_json = json.dumps(matrix_data, sort_keys=True)
    matrix_hash = hashlib.sha256(matrix_json.encode()).hexdigest()
    
    # 保存 hash
    hash_path = "runtime/eval/system_matrix.hash"
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(f"sha256:{matrix_hash}")
    
    print(f"System matrix hash: sha256:{matrix_hash}")
    return matrix_hash

if __name__ == "__main__":
    calculate_system_matrix_hash()


