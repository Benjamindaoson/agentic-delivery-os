"""
Human-in-the-loop (HITL) extension placeholder.
Scaffold for takeover, manual override, and rollback orchestration.
"""
from typing import Dict, Any

class HITLCoordinator:
    def __init__(self):
        pass

    def request_takeover(self, task_id: str, reason: str):
        """
        TODO: Implement notification, locking, and takeover workflow.
        - lock task
        - notify operators
        - provide replayable context + decision rationale
        """
        raise NotImplementedError("HITL flow not implemented")


