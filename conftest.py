import os
import sys
import time
import subprocess
from typing import Iterator

import pytest
import requests


def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def _wait_for_health(timeout: int = 30) -> None:
    base = "http://localhost:8000/api/health"
    for _ in range(timeout):
        try:
            resp = requests.get(base, timeout=1)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Backend health check did not become ready within timeout")


@pytest.fixture(scope="session", autouse=True)
def backend_server() -> Iterator[None]:
    """
    Start the FastAPI backend once per test session so integration tests
    hitting http://localhost:8000 can succeed. Uses uvicorn in a subprocess
    to avoid thread issues.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([env.get("PYTHONPATH", ""), _project_root()])
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, cwd=_project_root(), env=env)
    try:
        _wait_for_health()
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

