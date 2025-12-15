"""
Tenant fairness via token bucket.
"""
from typing import Dict
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.timestamp = time.time()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.timestamp
        self.timestamp = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class TenantQuota:
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}

    def configure(self, tenant_id: str, rate: float, capacity: float):
        self.buckets[tenant_id] = TokenBucket(rate, capacity)

    def allow(self, tenant_id: str, cost: float = 1.0) -> bool:
        bucket = self.buckets.get(tenant_id)
        if not bucket:
            return True
        return bucket.allow(cost)


tenant_quota_singleton = TenantQuota()


