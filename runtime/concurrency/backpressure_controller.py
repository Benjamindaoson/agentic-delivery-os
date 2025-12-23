"""
Backpressure Controller - Adaptive load management
L6 Component: Scale Layer - Load Control
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os


@dataclass
class BackpressureMetrics:
    """Metrics for backpressure decisions"""
    queue_depth: int
    queue_capacity: int
    avg_processing_time_ms: float
    error_rate: float
    memory_usage_pct: float
    cpu_usage_pct: float


@dataclass
class BackpressureState:
    """Current backpressure state"""
    level: str  # normal | warning | critical | overload
    throttle_factor: float  # 0.0-1.0, 1.0 = no throttling
    reject_new_requests: bool
    pause_non_critical: bool
    reason: str


class BackpressureController:
    """
    Adaptive backpressure management
    Protects system from overload
    """
    
    def __init__(
        self,
        max_queue_depth: int = 1000,
        warning_threshold: float = 0.7,
        critical_threshold: float = 0.9,
        artifacts_path: str = "artifacts/backpressure"
    ):
        self.max_queue_depth = max_queue_depth
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Current state
        self.state = BackpressureState(
            level="normal",
            throttle_factor=1.0,
            reject_new_requests=False,
            pause_non_critical=False,
            reason="System operating normally"
        )
        
        # Historical metrics
        self.metrics_history = []
        self.state_history = []
        
        # Statistics
        self.stats = {
            "state_changes": 0,
            "requests_rejected": 0,
            "requests_throttled": 0,
            "time_in_overload": 0.0
        }
    
    def evaluate(self, metrics: BackpressureMetrics) -> BackpressureState:
        """
        Evaluate current metrics and determine backpressure state
        """
        self.metrics_history.append({
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        })
        
        # Keep only last 100 metrics
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)
        
        # Calculate overall load score (0.0-1.0)
        queue_score = metrics.queue_depth / self.max_queue_depth
        error_score = min(1.0, metrics.error_rate * 10)  # Scale error rate
        memory_score = metrics.memory_usage_pct / 100.0
        cpu_score = metrics.cpu_usage_pct / 100.0
        
        # Weighted average
        load_score = (
            queue_score * 0.4 +
            error_score * 0.2 +
            memory_score * 0.2 +
            cpu_score * 0.2
        )
        
        # Determine state
        old_level = self.state.level
        
        if load_score >= self.critical_threshold:
            if metrics.queue_depth >= self.max_queue_depth:
                # Overload: reject new requests
                new_state = BackpressureState(
                    level="overload",
                    throttle_factor=0.0,
                    reject_new_requests=True,
                    pause_non_critical=True,
                    reason=f"Queue full ({metrics.queue_depth}/{self.max_queue_depth})"
                )
            else:
                # Critical: heavy throttling
                new_state = BackpressureState(
                    level="critical",
                    throttle_factor=0.3,
                    reject_new_requests=False,
                    pause_non_critical=True,
                    reason=f"Critical load: {load_score:.2f}"
                )
        
        elif load_score >= self.warning_threshold:
            # Warning: moderate throttling
            throttle_factor = 1.0 - ((load_score - self.warning_threshold) / (self.critical_threshold - self.warning_threshold)) * 0.7
            new_state = BackpressureState(
                level="warning",
                throttle_factor=throttle_factor,
                reject_new_requests=False,
                pause_non_critical=False,
                reason=f"Warning load: {load_score:.2f}"
            )
        
        else:
            # Normal: no throttling
            new_state = BackpressureState(
                level="normal",
                throttle_factor=1.0,
                reject_new_requests=False,
                pause_non_critical=False,
                reason="System operating normally"
            )
        
        # Update state
        self.state = new_state
        
        # Track state changes
        if old_level != new_state.level:
            self.stats["state_changes"] += 1
            self.state_history.append({
                "timestamp": datetime.now().isoformat(),
                "from": old_level,
                "to": new_state.level,
                "load_score": load_score
            })
        
        # Track overload time
        if new_state.level == "overload":
            self.stats["time_in_overload"] += 1.0  # Approximate
        
        return self.state
    
    def should_accept_request(
        self,
        priority: int = 5,
        is_critical: bool = False
    ) -> bool:
        """
        Determine if a new request should be accepted
        Args:
            priority: 1-10, higher is more important
            is_critical: If True, bypass some checks
        """
        if is_critical:
            return True
        
        if self.state.reject_new_requests:
            self.stats["requests_rejected"] += 1
            return False
        
        if self.state.pause_non_critical and priority < 7:
            self.stats["requests_rejected"] += 1
            return False
        
        # Probabilistic throttling based on throttle_factor
        import random
        if random.random() > self.state.throttle_factor:
            self.stats["requests_throttled"] += 1
            return False
        
        return True
    
    def get_recommended_delay(self) -> float:
        """Get recommended delay before next request (seconds)"""
        if self.state.level == "overload":
            return 5.0
        elif self.state.level == "critical":
            return 1.0
        elif self.state.level == "warning":
            return 0.1
        else:
            return 0.0
    
    def get_stats(self) -> Dict:
        """Get backpressure statistics"""
        return {
            "current_state": {
                "level": self.state.level,
                "throttle_factor": self.state.throttle_factor,
                "reject_new_requests": self.state.reject_new_requests,
                "reason": self.state.reason
            },
            "statistics": dict(self.stats),
            "recent_states": self.state_history[-10:] if self.state_history else []
        }
    
    def save_state(self):
        """Persist current state and statistics"""
        path = os.path.join(self.artifacts_path, "backpressure_state.json")
        with open(path, 'w') as f:
            json.dump(self.get_stats(), f, indent=2)


# Global backpressure controller
_controller: Optional[BackpressureController] = None

def get_backpressure_controller(
    max_queue_depth: int = 1000
) -> BackpressureController:
    """Get global backpressure controller"""
    global _controller
    if _controller is None:
        _controller = BackpressureController(max_queue_depth=max_queue_depth)
    return _controller



