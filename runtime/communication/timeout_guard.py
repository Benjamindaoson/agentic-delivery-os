"""
Timeout guard for agent calls.
"""
import time
from typing import Callable, Any, Dict


class TimeoutError(Exception):
    pass


def run_with_timeout(fn: Callable, args: tuple, kwargs: Dict[str, Any], timeout_ms: int):
    start = time.time()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.time() - start) * 1000
    if elapsed_ms > timeout_ms:
        raise TimeoutError(f"timeout {elapsed_ms}ms > {timeout_ms}ms")
    return result


