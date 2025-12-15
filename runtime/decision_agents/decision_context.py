"""
Decision context aggregator.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class DecisionContext:
    intent: Dict[str, Any]
    query: Dict[str, Any]
    ranking: Dict[str, Any]
    strategy: Dict[str, Any]

    def to_dict(self):
        return asdict(self)


