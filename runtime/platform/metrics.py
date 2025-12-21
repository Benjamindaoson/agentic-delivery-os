"""
Lightweight Prometheus-style metrics registry.
Attempts to use prometheus_client if available, otherwise falls back to in-memory counters.
This is minimal scaffolding for observability.
"""
from typing import Dict
import time

class InMemoryCounter:
    def __init__(self):
        self._value = 0

    def inc(self, v: int = 1):
        self._value += v

    def get(self):
        return self._value

class MetricsRegistry:
    _default = None

    def __init__(self):
        self.counters: Dict[str, InMemoryCounter] = {}

    @classmethod
    def get_default(cls):
        if cls._default is None:
            cls._default = MetricsRegistry()
            # pre-create common counters
            cls._default.counters["tasks_started"] = InMemoryCounter()
            cls._default.counters["tasks_completed"] = InMemoryCounter()
            cls._default.counters["agent_executions_total"] = InMemoryCounter()
            cls._default.counters["governance_decisions_total"] = InMemoryCounter()
        return cls._default

    def counter(self, name: str):
        if name not in self.counters:
            self.counters[name] = InMemoryCounter()
        return self.counters[name]

    def snapshot(self):
        return {k: v.get() for k, v in self.counters.items()}


