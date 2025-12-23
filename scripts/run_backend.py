import os
import sys

import uvicorn


def main() -> None:
    """
    Unified backend entrypoint for local run and CI.

    - Ensures repo root is on PYTHONPATH so `backend.*` and `runtime.*` imports resolve
    - Starts FastAPI app defined in `backend.main:app`
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, repo_root)

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()































