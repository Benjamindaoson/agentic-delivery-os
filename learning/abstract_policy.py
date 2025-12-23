"""
AbstractPolicy: Unified learning interface for Bandit / Offline RL / Meta-Learning.

All policy implementations must implement:
- encode_state(context) -> state representation
- select_action(state, **kwargs) -> action identifier
- compute_reward(outcome, **kwargs) -> float reward
- update(transition, **kwargs) -> training/learning step
- export_policy() -> serializable policy snapshot

Supports paradigm migration (Bandit -> RL) by keeping a consistent interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class AbstractPolicy(ABC):
    """Unified policy abstraction."""

    policy_id: str = "abstract"
    version: str = "1.0"

    @abstractmethod
    def encode_state(self, context: Dict[str, Any]) -> Any:
        """Encode arbitrary context into a model-usable state."""
        raise NotImplementedError

    @abstractmethod
    def select_action(self, state: Any, **kwargs) -> Any:
        """Select an action given encoded state."""
        raise NotImplementedError

    @abstractmethod
    def compute_reward(self, outcome: Dict[str, Any], **kwargs) -> float:
        """Compute reward from an outcome."""
        raise NotImplementedError

    @abstractmethod
    def update(self, transition: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Update policy using a transition:
        transition = {
            "state": ...,
            "action": ...,
            "reward": ...,
            "next_state": ...,
            "done": bool
        }
        """
        raise NotImplementedError

    @abstractmethod
    def export_policy(self) -> Dict[str, Any]:
        """Export a serializable snapshot of the policy."""
        raise NotImplementedError

    def migrate_to_rl(self) -> Dict[str, Any]:
        """
        Optional helper for paradigm migration (Bandit -> RL).
        Returns a minimal RL-ready snapshot.
        """
        return {
            "policy_id": getattr(self, "policy_id", "unknown"),
            "version": getattr(self, "version", "1.0"),
            "paradigm": "bandit_to_rl",
        }

