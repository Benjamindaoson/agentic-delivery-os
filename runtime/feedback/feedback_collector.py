"""
Online Feedback Injection Layer

Collects external feedback and persists to JSON for replay/diff.

Constraints:
- Async-friendly API
- Removable without affecting execution
- Output: artifacts/feedback_events.json
"""
import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


SUPPORTED_FEEDBACK = {
    "user_accept",
    "user_edit",
    "abort",
    "downstream_success",
    "human_override",
}


@dataclass
class FeedbackEvent:
    run_id: str
    feedback_type: str
    payload: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackCollector:
    """Collects and persists feedback events."""

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_path = os.path.join(artifacts_dir, "feedback_events.json")
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self._events: List[FeedbackEvent] = []
        self._load()

    async def record(
        self,
        run_id: str,
        feedback_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> FeedbackEvent:
        """
        Record a feedback event.

        Args:
            run_id: linked run id
            feedback_type: one of SUPPORTED_FEEDBACK
            payload: additional info
        """
        if feedback_type not in SUPPORTED_FEEDBACK:
            raise ValueError(f"Unsupported feedback_type: {feedback_type}")
        event = FeedbackEvent(
            run_id=run_id,
            feedback_type=feedback_type,
            payload=payload or {},
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)
        self._save()
        return event

    def list_events(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]

    def _load(self) -> None:
        if not os.path.exists(self.output_path):
            return
        try:
            with open(self.output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("events", []):
                self._events.append(
                    FeedbackEvent(
                        run_id=item.get("run_id", ""),
                        feedback_type=item.get("feedback_type", ""),
                        payload=item.get("payload", {}),
                        timestamp=item.get("timestamp", ""),
                    )
                )
        except (json.JSONDecodeError, IOError):
            return

    def _save(self) -> None:
        data = {
            "events": [e.to_dict() for e in self._events[-5000:]],
            "generated_at": datetime.now().isoformat(),
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)



