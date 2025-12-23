import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

RELEASE_STATE_DIR = os.path.join("artifacts", "release")
ACTIVE_POINTER_PATH = os.path.join(RELEASE_STATE_DIR, "active.json")
HISTORY_PATH = os.path.join(RELEASE_STATE_DIR, "history.jsonl")


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def promote(index_version: str, model_version: str = "default", config_version: str = "default") -> None:
    os.makedirs(RELEASE_STATE_DIR, exist_ok=True)
    current = _load_json(ACTIVE_POINTER_PATH)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "promote",
        "from": current if current else None,
        "to": {
            "index_version": index_version,
            "model_version": model_version,
            "config_version": config_version,
        },
    }
    # Append to history (audit log)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # Overwrite active pointer
    with open(ACTIVE_POINTER_PATH, "w", encoding="utf-8") as f:
        json.dump(entry["to"], f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.promote <index_version> [model_version] [config_version]")
        sys.exit(1)
    idx_ver = sys.argv[1]
    model_ver = sys.argv[2] if len(sys.argv) > 2 else "default"
    cfg_ver = sys.argv[3] if len(sys.argv) > 3 else "default"
    promote(idx_ver, model_ver, cfg_ver)































