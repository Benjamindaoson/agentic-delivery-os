"""
Industrial-Grade LLM Adapter
Production-ready adapter with:
- Error-rate based circuit breaker (sliding window)
- Real API cost tracking from response headers
- Latency simulation in mock mode
- Comprehensive observability
"""
import asyncio
import time
import os
import json
import random
from typing import Dict, Any, Tuple, List, Optional
from collections import deque
from datetime import datetime, timedelta

from runtime.llm.client_factory import create_llm_client
from runtime.config import load_effective_config
import yaml

# optional redis limiter
_redis_limiter = None
try:
    from runtime.llm.redis_rate_limiter import RedisRateLimiter
except Exception:
    RedisRateLimiter = None


class CircuitBreakerState:
    """Error-rate based circuit breaker with sliding window"""
    
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking all requests
    HALF_OPEN = "half_open"  # Testing if service recovered
    
    def __init__(
        self,
        error_rate_threshold: float = 0.5,
        window_size_seconds: int = 60,
        min_requests_in_window: int = 10,
        recovery_timeout_seconds: int = 30,
        half_open_max_requests: int = 3
    ):
        self.error_rate_threshold = error_rate_threshold
        self.window_size_seconds = window_size_seconds
        self.min_requests_in_window = min_requests_in_window
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_requests = half_open_max_requests
        
        self.state = self.CLOSED
        self.request_history: deque = deque()  # (timestamp, success: bool)
        self.last_state_change = time.time()
        self.half_open_successes = 0
        self.half_open_failures = 0
    
    def record_request(self, success: bool):
        """Record a request outcome"""
        now = time.time()
        self.request_history.append((now, success))
        
        # Prune old entries
        cutoff = now - self.window_size_seconds
        while self.request_history and self.request_history[0][0] < cutoff:
            self.request_history.popleft()
        
        # Handle half-open state
        if self.state == self.HALF_OPEN:
            if success:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_max_requests:
                    self._transition_to(self.CLOSED)
            else:
                self.half_open_failures += 1
                self._transition_to(self.OPEN)
            return
        
        # Check if we should trip the circuit
        if self.state == self.CLOSED:
            self._check_error_rate()
    
    def _check_error_rate(self):
        """Check error rate and trip circuit if needed"""
        if len(self.request_history) < self.min_requests_in_window:
            return  # Not enough data
        
        failures = sum(1 for _, success in self.request_history if not success)
        error_rate = failures / len(self.request_history)
        
        if error_rate >= self.error_rate_threshold:
            self._transition_to(self.OPEN)
    
    def _transition_to(self, new_state: str):
        """Transition to a new state"""
        self.state = new_state
        self.last_state_change = time.time()
        
        if new_state == self.HALF_OPEN:
            self.half_open_successes = 0
            self.half_open_failures = 0
    
    def allow_request(self) -> bool:
        """Check if a request should be allowed"""
        now = time.time()
        
        if self.state == self.CLOSED:
            return True
        
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if now - self.last_state_change >= self.recovery_timeout_seconds:
                self._transition_to(self.HALF_OPEN)
                return True
            return False
        
        if self.state == self.HALF_OPEN:
            # Allow limited requests in half-open
            total_half_open = self.half_open_successes + self.half_open_failures
            return total_half_open < self.half_open_max_requests
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        if self.request_history:
            failures = sum(1 for _, s in self.request_history if not s)
            error_rate = failures / len(self.request_history)
        else:
            error_rate = 0.0
        
        return {
            "state": self.state,
            "error_rate": error_rate,
            "requests_in_window": len(self.request_history),
            "last_state_change": datetime.fromtimestamp(self.last_state_change).isoformat()
        }


class CostTracker:
    """Real cost tracking from API responses"""
    
    # Pricing per 1K tokens (can be loaded from config)
    DEFAULT_PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "default": {"input": 0.001, "output": 0.002}
    }
    
    def __init__(self, pricing_config_path: str = "configs/price_table.yaml"):
        self.pricing = self._load_pricing(pricing_config_path)
        self.session_costs: List[Dict[str, Any]] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def _load_pricing(self, path: str) -> Dict[str, Dict[str, float]]:
        """Load pricing from config"""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    return cfg.get("models", self.DEFAULT_PRICING)
            except Exception:
                pass
        return self.DEFAULT_PRICING
    
    def compute_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        api_reported_cost: Optional[float] = None
    ) -> float:
        """Compute cost for a request"""
        # Prefer API-reported cost if available
        if api_reported_cost is not None:
            return api_reported_cost
        
        # Fallback to computed cost
        pricing = self.pricing.get(model, self.pricing.get("default"))
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost
    
    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        task_id: Optional[str] = None,
        tenant_id: str = "default"
    ):
        """Record usage for tracking"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "task_id": task_id,
            "tenant_id": tenant_id
        }
        self.session_costs.append(entry)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session cost summary"""
        return {
            "total_requests": len(self.session_costs),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 6),
            "avg_cost_per_request": round(self.total_cost / max(len(self.session_costs), 1), 6)
        }


class LLMAdapter:
    """Industrial-grade LLM adapter with comprehensive production features"""
    
    def __init__(self, config_path: str = "configs/system.yaml"):
        self.client = create_llm_client(config_path)
        self.config_path = config_path
        self._last_call_ts = 0.0
        self._min_interval = 0.0
        self.cost_accounting = []
        
        # Per-model components
        self._model_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        
        # Per-tenant rate timestamps
        self._tenant_last_ts: Dict[str, float] = {}
        
        # Cost tracker
        self.cost_tracker = CostTracker()
        
        # Load config
        self._load_config(config_path)
    
    def _load_config(self, config_path: str):
        """Load configuration"""
        try:
            cfg_path = os.environ.get("SYSTEM_CONFIG_PATH", config_path)
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                llm_cfg = cfg.get("llm", {})
                self._min_interval = float(llm_cfg.get("min_interval_sec", 0.0))
                self._circuit_error_threshold = float(llm_cfg.get("circuit_error_rate_threshold", 0.5))
                self._circuit_window = int(llm_cfg.get("circuit_window_seconds", 60))
                self._circuit_min_requests = int(llm_cfg.get("circuit_min_requests", 10))
                self._circuit_recovery = int(llm_cfg.get("circuit_recovery_seconds", 30))
                self._mock_latency_range = llm_cfg.get("mock_latency_range", [100, 500])
                self._mock_error_rate = float(llm_cfg.get("mock_error_rate", 0.0))
            else:
                self._circuit_error_threshold = 0.5
                self._circuit_window = 60
                self._circuit_min_requests = 10
                self._circuit_recovery = 30
                self._mock_latency_range = [100, 500]
                self._mock_error_rate = 0.0
        except Exception:
            self._circuit_error_threshold = 0.5
            self._circuit_window = 60
            self._circuit_min_requests = 10
            self._circuit_recovery = 30
            self._mock_latency_range = [100, 500]
            self._mock_error_rate = 0.0
    
    def _get_circuit_breaker(self, model: str) -> CircuitBreakerState:
        """Get or create circuit breaker for model"""
        if model not in self._circuit_breakers:
            self._circuit_breakers[model] = CircuitBreakerState(
                error_rate_threshold=self._circuit_error_threshold,
                window_size_seconds=self._circuit_window,
                min_requests_in_window=self._circuit_min_requests,
                recovery_timeout_seconds=self._circuit_recovery
            )
        return self._circuit_breakers[model]

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        meta: Dict[str, Any] = None,
        task_id: str = None,
        tenant_id: str = "default",
        model: str = None,
        timeout: float = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Industrial-grade unified call entry for all agents.
        
        Features:
        - Error-rate based circuit breaker (sliding window)
        - Per-tenant and per-model rate limiting
        - Retries with exponential backoff
        - Real cost tracking from API responses
        - Mock mode with realistic latency and error simulation
        """
        meta = meta or {}
        now = time.time()
        call_start = time.time()
        
        model_key = model or getattr(self.client, "model_name", "default")
        provider = getattr(self.client, "get_provider_name", lambda: "unknown")()
        
        # Check circuit breaker FIRST (error-rate based)
        circuit_breaker = self._get_circuit_breaker(model_key)
        if not circuit_breaker.allow_request():
            cb_stats = circuit_breaker.get_stats()
            return ({}, {
                "llm_used": False,
                "fallback_used": True,
                "failure_code": "circuit_open",
                "circuit_breaker_state": cb_stats["state"],
                "error_rate": cb_stats["error_rate"],
                "provider": provider,
                "model_name": model_key
            })
        
        # Tenant rate limiting: prefer Redis-backed limiter
        cfg = load_effective_config()
        redis_url = (cfg.get("database", {}).get("redis_url") or 
                     cfg.get("redis", {}).get("url") if cfg.get("redis") else None)
        limiter_allowed = True
        
        if redis_url and RedisRateLimiter:
            global _redis_limiter
            if _redis_limiter is None:
                try:
                    _redis_limiter = RedisRateLimiter(
                        redis_url,
                        window_seconds=1,
                        limit=cfg.get("llm", {}).get("rate_per_second", 5)
                    )
                    await _redis_limiter.initialize()
                except Exception:
                    _redis_limiter = None
            if _redis_limiter:
                limiter_allowed = await _redis_limiter.allow(tenant_id=tenant_id, model=model_key)
        
        if not limiter_allowed:
            return ({}, {
                "llm_used": False,
                "fallback_used": True,
                "failure_code": "rate_limited",
                "provider": provider,
                "model_name": model_key
            })
        
        # Fallback to local min-interval if no redis limiter
        if not _redis_limiter:
            last_t = self._tenant_last_ts.get(tenant_id, 0.0)
            if now - last_t < self._min_interval:
                await asyncio.sleep(self._min_interval - (now - last_t))
            self._tenant_last_ts[tenant_id] = time.time()
        
        # Model semaphore for concurrency isolation
        if model_key not in self._model_semaphores:
            self._model_semaphores[model_key] = asyncio.Semaphore(4)
        
        # Retries with exponential backoff
        retries = 0
        max_retries = getattr(self.client, "max_retries", 2)
        backoff_base = 0.5
        last_error = None
        
        async with self._model_semaphores[model_key]:
            while retries <= max_retries:
                try:
                    # Check if mock mode should simulate errors
                    is_mock = os.environ.get("LLM_MODE", "mock") == "mock"
                    if is_mock and self._mock_error_rate > 0:
                        if random.random() < self._mock_error_rate:
                            raise Exception("Simulated mock error")
                        # Simulate realistic latency in mock mode
                        latency_ms = random.randint(*self._mock_latency_range)
                        await asyncio.sleep(latency_ms / 1000)
                    
                    # Actual call to client
                    result, meta_out = await self.client.generate_json(
                        system_prompt, user_prompt, schema, meta
                    )
                    
                    # Extract real usage from response
                    usage = meta_out.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                    api_cost = usage.get("cost")  # Some APIs return this
                    
                    # Compute and record cost
                    computed_cost = self.cost_tracker.compute_cost(
                        model=model_key,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        api_reported_cost=api_cost
                    )
                    
                    self.cost_tracker.record_usage(
                        model=model_key,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=computed_cost,
                        task_id=task_id,
                        tenant_id=tenant_id
                    )
                    
                    # Record success with circuit breaker
                    circuit_breaker.record_request(success=True)
                    
                    # Add cost info to meta
                    meta_out["cost"] = computed_cost
                    meta_out["input_tokens"] = input_tokens
                    meta_out["output_tokens"] = output_tokens
                    meta_out["latency_ms"] = (time.time() - call_start) * 1000
                    meta_out["retries"] = retries
                    
                    # Record to artifact
                    self._record_cost_meta(meta_out, task_id=task_id, model=model_key, tenant_id=tenant_id)
                    
                    return result, meta_out
                    
                except Exception as e:
                    last_error = e
                    retries += 1
                    
                    # Record failure with circuit breaker
                    circuit_breaker.record_request(success=False)
                    
                    if retries > max_retries:
                        break
                    
                    await asyncio.sleep(backoff_base * (2 ** (retries - 1)))
        
        # All retries exhausted - return fallback
        meta_out = {
            "llm_used": False,
            "fallback_used": True,
            "failure_code": "max_retries_exceeded",
            "error": str(last_error),
            "provider": provider,
            "model_name": model_key,
            "retries": retries,
            "circuit_breaker_state": circuit_breaker.get_stats()["state"],
            "latency_ms": (time.time() - call_start) * 1000
        }
        self._record_cost_meta(meta_out, task_id=task_id, model=model_key, tenant_id=tenant_id)
        return {}, meta_out

    def _record_cost_meta(
        self,
        meta: Dict[str, Any],
        task_id: str = None,
        model: str = None,
        tenant_id: str = None
    ):
        """Record cost metadata into artifact with real cost tracking."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": meta.get("provider"),
            "model": meta.get("model_name", model),
            "retries": meta.get("retries", 0),
            "fallback_used": meta.get("fallback_used", False),
            "failure_code": meta.get("failure_code"),
            "prompt_hash": meta.get("prompt_hash"),
            "llm_used": meta.get("llm_used", True),
            # Real cost from CostTracker
            "cost": meta.get("cost", 0.0),
            "input_tokens": meta.get("input_tokens", 0),
            "output_tokens": meta.get("output_tokens", 0),
            "latency_ms": meta.get("latency_ms", 0),
            "circuit_breaker_state": meta.get("circuit_breaker_state"),
            "tenant_id": tenant_id
        }
        
        self.cost_accounting.append(entry)
        
        if task_id:
            try:
                artifact_dir = os.path.join("artifacts", "rag_project", task_id)
                os.makedirs(artifact_dir, exist_ok=True)
                cost_path = os.path.join(artifact_dir, "cost_report.json")
                
                # Append to existing
                existing = []
                if os.path.exists(cost_path):
                    with open(cost_path, "r", encoding="utf-8") as f:
                        existing = json.load(f) or []
                existing.append(entry)
                
                with open(cost_path, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    
    def get_circuit_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker stats for all models"""
        return {
            model: cb.get_stats()
            for model, cb in self._circuit_breakers.items()
        }
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary from CostTracker"""
        return self.cost_tracker.get_session_summary()


