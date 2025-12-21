"""
Runtime configuration loader: merges system and runtime configs, supports env overrides.
"""
import os
import yaml

def load_effective_config(system_path: str = "configs/system.yaml", runtime_path: str = "configs/runtime.yaml") -> dict:
    cfg = {}
    try:
        if os.path.exists(system_path):
            with open(system_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}
    try:
        if os.path.exists(runtime_path):
            with open(runtime_path, "r", encoding="utf-8") as f:
                runtime_cfg = yaml.safe_load(f) or {}
                # shallow merge runtime into system
                for k, v in runtime_cfg.items():
                    if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                        cfg[k].update(v)
                    else:
                        cfg[k] = v
    except Exception:
        pass

    # env overrides (simple)
    env_db = os.environ.get("DATABASE_URL")
    if env_db:
        cfg.setdefault("database", {})["url"] = env_db
    env_mode = os.environ.get("LLM_MODE")
    if env_mode:
        cfg.setdefault("llm", {})["mode"] = env_mode

    return cfg

def print_effective_config():
    cfg = load_effective_config()
    # hide secrets
    safe = {k: (v if k.lower() not in ("api_key", "password", "secret") else "*****") for k, v in cfg.items()}
    import json
    print("Effective runtime config:", json.dumps(safe, indent=2))


