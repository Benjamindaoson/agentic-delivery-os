import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

RELEASE_STATE_DIR = os.path.join("artifacts", "release")
ACTIVE_POINTER_PATH = os.path.join(RELEASE_STATE_DIR, "active.json")
HISTORY_PATH = os.path.join(RELEASE_STATE_DIR, "history.jsonl")


def _load_history() -> Any:
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    import json as _json
    return [_json.loads(line) for line in lines]


def rollback() -> None:
    os.makedirs(RELEASE_STATE_DIR, exist_ok=True)
    history = _load_history()
    if len(history) < 1:
        print("No history available for rollback.")
        return
    last = history[-1]
    previous = last.get("from")
    if previous is None:
        print("No previous stable state to rollback to.")
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "rollback",
        "from": last.get("to"),
        "to": previous,
    }
    # Append rollback entry
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # Overwrite active pointer
    with open(ACTIVE_POINTER_PATH, "w", encoding="utf-8") as f:
        json.dump(previous, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    rollback()
























