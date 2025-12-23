"""
Rate Limiter - Token bucket based rate limiting
L6 Component: Scale Layer - Rate Control
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import threading
import json
import os


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests_per_second: float
    max_burst: int
    cost_per_request: float = 1.0


class TokenBucket:
    """Token bucket algorithm implementation"""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens
        Returns True if successful, False if rate limited
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Refill tokens
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now
            
            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def wait_for_tokens(self, tokens: float = 1.0, timeout: float = None) -> bool:
        """Wait until tokens are available"""
        start = time.time()
        
        while True:
            if self.consume(tokens):
                return True
            
            if timeout and (time.time() - start) > timeout:
                return False
            
            # Calculate wait time
            with self.lock:
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.rate if needed_tokens > 0 else 0.01
            
            time.sleep(min(wait_time, 0.1))


class RateLimiter:
    """
    Multi-dimensional rate limiter
    Supports per-tenant, per-agent, and global rate limits
    """
    
    def __init__(
        self,
        global_config: RateLimitConfig,
        artifacts_path: str = "artifacts/rate_limits"
    ):
        self.global_config = global_config
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Global bucket
        self.global_bucket = TokenBucket(
            rate=global_config.max_requests_per_second,
            capacity=global_config.max_burst
        )
        
        # Per-tenant buckets
        self.tenant_buckets: Dict[str, TokenBucket] = {}
        self.tenant_configs: Dict[str, RateLimitConfig] = {}
        
        # Per-agent buckets
        self.agent_buckets: Dict[str, TokenBucket] = {}
        self.agent_configs: Dict[str, RateLimitConfig] = {}
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "rate_limited": 0,
            "by_tenant": {},
            "by_agent": {}
        }
    
    def set_tenant_limit(self, tenant_id: str, config: RateLimitConfig):
        """Set rate limit for a specific tenant"""
        self.tenant_configs[tenant_id] = config
        self.tenant_buckets[tenant_id] = TokenBucket(
            rate=config.max_requests_per_second,
            capacity=config.max_burst
        )
    
    def set_agent_limit(self, agent_id: str, config: RateLimitConfig):
        """Set rate limit for a specific agent"""
        self.agent_configs[agent_id] = config
        self.agent_buckets[agent_id] = TokenBucket(
            rate=config.max_requests_per_second,
            capacity=config.max_burst
        )
    
    def check_limit(
        self,
        tenant_id: str = "default",
        agent_id: str = "default",
        cost: float = 1.0
    ) -> bool:
        """
        Check if request is allowed
        Returns True if allowed, False if rate limited
        """
        self.stats["total_requests"] += 1
        
        # Check global limit
        if not self.global_bucket.consume(cost):
            self.stats["rate_limited"] += 1
            return False
        
        # Check tenant limit
        if tenant_id in self.tenant_buckets:
            if not self.tenant_buckets[tenant_id].consume(cost):
                self.stats["rate_limited"] += 1
                self.stats["by_tenant"][tenant_id] = (
                    self.stats["by_tenant"].get(tenant_id, 0) + 1
                )
                return False
        
        # Check agent limit
        if agent_id in self.agent_buckets:
            if not self.agent_buckets[agent_id].consume(cost):
                self.stats["rate_limited"] += 1
                self.stats["by_agent"][agent_id] = (
                    self.stats["by_agent"].get(agent_id, 0) + 1
                )
                return False
        
        return True
    
    def wait_for_limit(
        self,
        tenant_id: str = "default",
        agent_id: str = "default",
        cost: float = 1.0,
        timeout: float = 10.0
    ) -> bool:
        """Wait until request is allowed"""
        start = time.time()
        
        # Wait for global
        if not self.global_bucket.wait_for_tokens(cost, timeout):
            return False
        
        remaining_timeout = timeout - (time.time() - start)
        
        # Wait for tenant
        if tenant_id in self.tenant_buckets:
            if not self.tenant_buckets[tenant_id].wait_for_tokens(cost, remaining_timeout):
                return False
        
        remaining_timeout = timeout - (time.time() - start)
        
        # Wait for agent
        if agent_id in self.agent_buckets:
            if not self.agent_buckets[agent_id].wait_for_tokens(cost, remaining_timeout):
                return False
        
        return True
    
    def get_stats(self) -> Dict:
        """Get rate limiting statistics"""
        return {
            "total_requests": self.stats["total_requests"],
            "rate_limited": self.stats["rate_limited"],
            "rate_limited_pct": (
                self.stats["rate_limited"] / self.stats["total_requests"] * 100
                if self.stats["total_requests"] > 0 else 0
            ),
            "by_tenant": dict(self.stats["by_tenant"]),
            "by_agent": dict(self.stats["by_agent"])
        }
    
    def save_stats(self):
        """Persist statistics"""
        path = os.path.join(self.artifacts_path, "rate_limit_stats.json")
        with open(path, 'w') as f:
            json.dump(self.get_stats(), f, indent=2)


# Global rate limiter
_limiter: Optional[RateLimiter] = None

def get_rate_limiter(
    max_rps: float = 100.0,
    max_burst: int = 200
) -> RateLimiter:
    """Get global rate limiter"""
    global _limiter
    if _limiter is None:
        config = RateLimitConfig(
            max_requests_per_second=max_rps,
            max_burst=max_burst
        )
        _limiter = RateLimiter(config)
    return _limiter



