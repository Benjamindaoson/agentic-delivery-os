"""
Agent-level scheduler: concurrency cap, rate limit, isolation class, tenant fairness, backpressure.
"""
from typing import Dict, Any
import time
from collections import defaultdict
from runtime.scheduler.tenant_quota import tenant_quota_singleton
from runtime.scheduler.backpressure import compute_backpressure


class AgentScheduler:
    def __init__(self):
        self.concurrency_cap = defaultdict(lambda: 5)
        self.active_counts = defaultdict(int)
        self.rate_limit = defaultdict(lambda: {"last_ts": 0.0, "min_interval": 0.01})
        self.isolation_class = defaultdict(lambda: "standard")

    def configure_agent(self, agent_id: str, concurrency: int, min_interval: float, isolation: str):
        self.concurrency_cap[agent_id] = concurrency
        self.rate_limit[agent_id]["min_interval"] = min_interval
        self.isolation_class[agent_id] = isolation

    def allow(self, agent_id: str, tenant_id: str, system_metrics: Dict[str, float]) -> Dict[str, Any]:
        # Backpressure
        bp = compute_backpressure(system_metrics)
        if bp == "HIGH":
            return {"allowed": False, "reason": "backpressure_high"}

        # Rate limit
        now = time.time()
        rl = self.rate_limit[agent_id]
        if now - rl["last_ts"] < rl["min_interval"]:
            return {"allowed": False, "reason": "rate_limit"}
        rl["last_ts"] = now

        # Concurrency cap
        if self.active_counts[agent_id] >= self.concurrency_cap[agent_id]:
            return {"allowed": False, "reason": "concurrency_cap"}

        # Tenant quota
        if not tenant_quota_singleton.allow(tenant_id):
            return {"allowed": False, "reason": "tenant_quota"}

        self.active_counts[agent_id] += 1
        return {"allowed": True, "reason": "ok"}

    def release(self, agent_id: str):
        if self.active_counts[agent_id] > 0:
            self.active_counts[agent_id] -= 1


agent_scheduler_singleton = AgentScheduler()


