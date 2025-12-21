"""
Provider-grade LLM adapter scaffold.
Wraps an underlying LLMClient and provides:
- rate limiting (simple token bucket scaffold)
- retry with backoff hooks
- cost accounting hooks (stubbed)
This is a scaffold; real production adapters should implement robust async rate-limiters and billing hooks.
"""
import asyncio
import time
from typing import Dict, Any, Tuple

from runtime.llm.client_factory import create_llm_client
from runtime.config import load_effective_config
from typing import Optional
import yaml

# optional redis limiter
_redis_limiter = None
try:
    from runtime.llm.redis_rate_limiter import RedisRateLimiter
except Exception:
    RedisRateLimiter = None

class LLMAdapter:
    def __init__(self, config_path: str = "configs/system.yaml"):
        self.client = create_llm_client(config_path)
        self._last_call_ts = 0.0
        self._min_interval = 0.0  # seconds, can be set via config
        self.cost_accounting = []  # list of cost events (stub)
        # concurrency isolation per model
        self._model_semaphores = {}
        # simple circuit breaker state per model
        self._failure_counts = {}
        self._circuit_open = {}
        # per-tenant rate timestamps
        self._tenant_last_ts = {}
        # load config hints
        try:
            import yaml, os
            cfg_path = os.environ.get("SYSTEM_CONFIG_PATH", config_path)
            if os.path.exists(cfg_path):
                cfg = yaml.safe_load(open(cfg_path, "r", encoding="utf-8")) or {}
                llm_cfg = cfg.get("llm", {})
                self._min_interval = float(llm_cfg.get("min_interval_sec", self._min_interval))
                self._circuit_threshold = int(llm_cfg.get("circuit_failure_threshold", 5))
                self._circuit_reset_seconds = int(llm_cfg.get("circuit_reset_seconds", 300))
            else:
                self._circuit_threshold = 5
                self._circuit_reset_seconds = 300
        except Exception:
            self._circuit_threshold = 5
            self._circuit_reset_seconds = 300

    async def call(self, system_prompt: str, user_prompt: str, schema: Dict[str, Any], meta: Dict[str, Any] = None, task_id: str = None, tenant_id: str = "default", model: str = None, timeout: float = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Unified call entry for all agents.
        - Enforces per-tenant and per-model rate limiting
        - Retries with exponential backoff
        - Simple circuit breaker per model
        - Records cost meta into artifact cost_report.json if task_id provided
        - Honors LLM_MODE (mock|real|replay) via client factory
        """
        meta = meta or {}
        now = time.time()

        # tenant rate limiting: prefer Redis-backed limiter if configured
        cfg = load_effective_config()
        redis_url = cfg.get("database", {}).get("redis_url") or cfg.get("redis", {}).get("url") if cfg.get("redis") else None
        limiter_allowed = True
        if redis_url and RedisRateLimiter:
            global _redis_limiter
            if _redis_limiter is None:
                try:
                    _redis_limiter = RedisRateLimiter(redis_url, window_seconds=1, limit=cfg.get("llm", {}).get("rate_per_second", 5))
                    await _redis_limiter.initialize()
                except Exception:
                    _redis_limiter = None
            if _redis_limiter:
                limiter_allowed = await _redis_limiter.allow(tenant_id=tenant_id, model=model or "default")
        if not limiter_allowed:
            return ({}, {"llm_used": False, "fallback_used": True, "failure_code": "rate_limited", "provider": getattr(self.client, "get_provider_name", lambda: "unknown")()})

        # fallback to local min-interval if no redis limiter
        if not _redis_limiter:
            last_t = self._tenant_last_ts.get(tenant_id, 0.0)
            if now - last_t < self._min_interval:
                await asyncio.sleep(self._min_interval - (now - last_t))
            self._tenant_last_ts[tenant_id] = time.time()

        # model semaphore for concurrency isolation
        model_key = model or getattr(self.client, "model_name", "default")
        if model_key not in self._model_semaphores:
            self._model_semaphores[model_key] = asyncio.Semaphore(4)  # default concurrency per model

        # circuit breaker check
        if self._circuit_open.get(model_key, False):
            # circuit is open -> immediate fallback to mock or raise
            return ({}, {"llm_used": False, "fallback_used": True, "failure_code": "circuit_open", "provider": getattr(self.client, "get_provider_name", lambda: "unknown")()})

        # retries with exponential backoff
        retries = 0
        max_retries = getattr(self.client, "max_retries", 2)
        backoff_base = 0.5

        async with self._model_semaphores[model_key]:
            while True:
                try:
                    # actual call to client
                    result, meta_out = await self.client.generate_json(system_prompt, user_prompt, schema, meta)
                    # cost accounting and trace write
                    self._record_cost_meta(meta_out, task_id=task_id, model=model_key, tenant_id=tenant_id)
                    # reset failure count on success
                    self._failure_counts[model_key] = 0
                    return result, meta_out
                except Exception as e:
                    retries += 1
                    self._failure_counts[model_key] = self._failure_counts.get(model_key, 0) + 1
                    if self._failure_counts[model_key] >= self._circuit_threshold:
                        self._circuit_open[model_key] = True
                    if retries > max_retries:
                        # return fallback
                        failure_code = getattr(e, "args", [str(e)])[0]
                        meta_out = {
                            "llm_used": False,
                            "fallback_used": True,
                            "failure_code": "max_retries_exceeded",
                            "error": str(e),
                            "provider": getattr(self.client, "get_provider_name", lambda: "unknown")(),
                            "model_name": model_key
                        }
                        self._record_cost_meta(meta_out, task_id=task_id, model=model_key, tenant_id=tenant_id)
                        return {}, meta_out
                    await asyncio.sleep(backoff_base * (2 ** (retries - 1)))

    def _record_cost_meta(self, meta: Dict[str, Any], task_id: str = None, model: str = None, tenant_id: str = None):
        """Record cost metadata into in-memory list and artifact if task_id provided."""
        entry = {
            "timestamp": time.time(),
            "provider": meta.get("provider"),
            "model": meta.get("model_name", model),
            "retries": meta.get("retries", 0),
            "fallback_used": meta.get("fallback_used", False),
            "failure_code": meta.get("failure_code"),
            "prompt_hash": meta.get("prompt_hash"),
        }
        # Estimate cost using price table config if available
        estimated_cost = 0.0
        try:
            # sampling tokens preference
            sampling = meta.get("sampling_params", {}) or {}
            max_tokens = int(sampling.get("max_tokens", 0) or 0)
            # load price table
            price_cfg = {}
            try:
                with open("configs/price_table.yaml", "r", encoding="utf-8") as pf:
                    price_cfg = yaml.safe_load(pf) or {}
            except Exception:
                price_cfg = {}
            model_prices = price_cfg.get("models", {})
            default_price = price_cfg.get("default_price_per_token", 0.000001)
            price_per_token = model_prices.get(model, default_price)
            estimated_cost = round(max_tokens * float(price_per_token), 8)
        except Exception:
            estimated_cost = 0.0
        entry["estimated_cost"] = estimated_cost
        self.cost_accounting.append(entry)
        if task_id:
            try:
                import os, json
                artifact_dir = os.path.join("artifacts", "rag_project", task_id)
                os.makedirs(artifact_dir, exist_ok=True)
                cost_path = os.path.join(artifact_dir, "cost_report.json")
                # append or create list
                existing = []
                if os.path.exists(cost_path):
                    with open(cost_path, "r", encoding="utf-8") as f:
                        existing = json.load(f) or []
                existing.append(entry)
                with open(cost_path, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    # legacy stub removed; use the structured _record_cost_meta above


