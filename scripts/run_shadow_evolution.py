#!/usr/bin/env python3
"""
Shadow Evolution Runner: 24h burn-in verification for Learning + Strategy + Bandit stability.

Usage:
    python scripts/run_shadow_evolution.py --duration 60 --candidates 3

This script:
1. Reads historical runs (or generates synthetic)
2. Executes active policy (read-only) and N candidate policies (shadow-only)
3. Monitors 4 stability metrics: candidate count, strategy entropy, KPI variance, bandit distribution
4. Hard-stops on circuit breaker conditions
"""
import os
import sys
import json
import math
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class StabilityMetrics:
    """Stability metrics tracked during shadow evolution."""
    timestamp: str
    candidate_policy_count: int
    strategy_entropy: float  # Higher = more diverse selection
    kpi_variance: float  # Rolling window variance
    bandit_selection_distribution: Dict[str, float]  # policy_id -> selection ratio
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HardStopEvent:
    """Circuit breaker trigger event."""
    timestamp: str
    reason: str
    metric_name: str
    metric_value: float
    threshold: float
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowEvolutionRunner:
    """
    Shadow Evolution Runner for stability verification.
    
    Monitors:
    - candidate_policy_count: Should not grow exponentially
    - strategy_entropy: Should not collapse to 0 (single strategy)
    - kpi_variance: Should not explode
    - bandit_selection_distribution: Should not collapse
    """
    
    # Circuit breaker thresholds (configurable via env)
    MAX_CANDIDATE_GROWTH_RATE = float(os.environ.get("MAX_CANDIDATE_GROWTH_RATE", "2.0"))
    MIN_STRATEGY_ENTROPY = float(os.environ.get("MIN_STRATEGY_ENTROPY", "0.1"))
    MAX_KPI_VARIANCE = float(os.environ.get("MAX_KPI_VARIANCE", "100.0"))
    MIN_BANDIT_DIVERSITY = float(os.environ.get("MIN_BANDIT_DIVERSITY", "0.05"))
    MAX_FAILURE_BUDGET_SPENT = float(os.environ.get("MAX_FAILURE_BUDGET_SPENT", "0.9"))
    
    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        num_candidates: int = 3,
        window_size: int = 100
    ):
        self.artifacts_dir = artifacts_dir
        self.num_candidates = num_candidates
        self.window_size = window_size
        
        # State
        self.metrics_history: List[StabilityMetrics] = []
        self.hard_stop_event: Optional[HardStopEvent] = None
        self.kpi_buffer: List[float] = []
        self.candidate_count_history: List[int] = []
        self.selection_counts: Dict[str, int] = defaultdict(int)
        self.total_selections: int = 0
        self.failure_budget_spent: float = 0.0
        self.failure_budget_total: float = 100.0
        
        # Policies (simulated)
        self.active_policy = "active_v1"
        self.candidate_policies: List[str] = []
    
    def run(self, duration_seconds: int = 60, tick_interval: float = 1.0) -> Dict[str, Any]:
        """
        Run shadow evolution for specified duration.
        
        Args:
            duration_seconds: Total duration in seconds
            tick_interval: Seconds between ticks
            
        Returns:
            Summary of the run
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=duration_seconds)
        tick = 0
        
        print(f"[Shadow Evolution] Starting burn-in for {duration_seconds}s")
        print(f"[Shadow Evolution] Active policy: {self.active_policy}")
        print(f"[Shadow Evolution] Candidates: {self.num_candidates}")
        
        # Initialize candidates
        self.candidate_policies = [f"candidate_v{i}" for i in range(1, self.num_candidates + 1)]
        
        while datetime.now() < end_time:
            tick += 1
            
            # Simulate a run
            run_result = self._simulate_run(tick)
            
            # Update metrics
            metrics = self._compute_metrics(tick)
            self.metrics_history.append(metrics)
            
            # Check circuit breakers
            stop_event = self._check_circuit_breakers(metrics, tick)
            if stop_event:
                self.hard_stop_event = stop_event
                print(f"[HARD STOP] {stop_event.reason}: {stop_event.metric_name}={stop_event.metric_value} (threshold={stop_event.threshold})")
                break
            
            # Progress
            if tick % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"[Shadow Evolution] Tick {tick}, elapsed={elapsed:.1f}s, candidates={len(self.candidate_policies)}, entropy={metrics.strategy_entropy:.3f}")
            
            # Sleep (in real impl, would process actual runs)
            import time
            time.sleep(tick_interval)
        
        # Save artifacts
        self._save_artifacts()
        
        return self._generate_summary(start_time)
    
    def _simulate_run(self, tick: int) -> Dict[str, Any]:
        """Simulate a single run with active + shadow policies."""
        # Active policy result (read-only)
        active_success = random.random() > 0.15  # 85% success rate
        active_cost = random.uniform(0.05, 0.15)
        active_latency = random.uniform(100, 300)
        
        # Shadow results for each candidate
        shadow_results = {}
        for candidate in self.candidate_policies:
            success = random.random() > 0.18  # Slightly worse initially
            cost = random.uniform(0.04, 0.16)
            latency = random.uniform(90, 320)
            shadow_results[candidate] = {
                "success": success,
                "cost": cost,
                "latency": latency
            }
        
        # Bandit selection (simulated Thompson Sampling)
        selected = self._bandit_select()
        self.selection_counts[selected] += 1
        self.total_selections += 1
        
        # Update KPI buffer
        kpi = 1.0 if active_success else 0.0
        self.kpi_buffer.append(kpi)
        if len(self.kpi_buffer) > self.window_size:
            self.kpi_buffer = self.kpi_buffer[-self.window_size:]
        
        # Occasionally spawn new candidates (simulated evolution)
        if tick % 20 == 0 and random.random() > 0.7:
            new_candidate = f"candidate_v{len(self.candidate_policies) + 1}"
            self.candidate_policies.append(new_candidate)
        
        # Track candidate count
        self.candidate_count_history.append(len(self.candidate_policies))
        
        # Consume failure budget (simulated)
        if not active_success:
            self.failure_budget_spent += 1.0
        
        return {
            "tick": tick,
            "active": {"success": active_success, "cost": active_cost, "latency": active_latency},
            "shadow": shadow_results,
            "selected": selected
        }
    
    def _bandit_select(self) -> str:
        """Simulated Thompson Sampling selection."""
        all_policies = [self.active_policy] + self.candidate_policies
        
        # Simple Thompson Sampling with Beta distributions
        samples = {}
        for policy in all_policies:
            successes = self.selection_counts.get(policy, 0) + 1
            failures = max(1, self.total_selections // len(all_policies) - successes)
            samples[policy] = random.betavariate(successes, max(1, failures))
        
        return max(samples, key=samples.get)
    
    def _compute_metrics(self, tick: int) -> StabilityMetrics:
        """Compute current stability metrics."""
        # Candidate count
        candidate_count = len(self.candidate_policies)
        
        # Strategy entropy
        if self.total_selections > 0:
            distribution = {
                p: self.selection_counts[p] / self.total_selections
                for p in [self.active_policy] + self.candidate_policies
            }
            entropy = self._compute_entropy(list(distribution.values()))
        else:
            distribution = {}
            entropy = 0.0
        
        # KPI variance
        if len(self.kpi_buffer) > 1:
            mean = sum(self.kpi_buffer) / len(self.kpi_buffer)
            variance = sum((x - mean) ** 2 for x in self.kpi_buffer) / len(self.kpi_buffer)
        else:
            variance = 0.0
        
        return StabilityMetrics(
            timestamp=datetime.now().isoformat(),
            candidate_policy_count=candidate_count,
            strategy_entropy=entropy,
            kpi_variance=variance,
            bandit_selection_distribution=distribution
        )
    
    def _compute_entropy(self, probs: List[float]) -> float:
        """Compute Shannon entropy of a distribution."""
        entropy = 0.0
        for p in probs:
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def _check_circuit_breakers(self, metrics: StabilityMetrics, tick: int) -> Optional[HardStopEvent]:
        """Check all circuit breaker conditions."""
        # 1. Candidate exponential growth
        if len(self.candidate_count_history) > 10:
            recent = self.candidate_count_history[-10:]
            growth_rate = recent[-1] / max(1, recent[0])
            if growth_rate > self.MAX_CANDIDATE_GROWTH_RATE:
                return HardStopEvent(
                    timestamp=datetime.now().isoformat(),
                    reason="candidate_exponential_growth",
                    metric_name="growth_rate",
                    metric_value=growth_rate,
                    threshold=self.MAX_CANDIDATE_GROWTH_RATE,
                    details={"recent_counts": recent}
                )
        
        # 2. Strategy entropy collapse
        if tick > 20 and metrics.strategy_entropy < self.MIN_STRATEGY_ENTROPY:
            return HardStopEvent(
                timestamp=datetime.now().isoformat(),
                reason="strategy_entropy_collapse",
                metric_name="strategy_entropy",
                metric_value=metrics.strategy_entropy,
                threshold=self.MIN_STRATEGY_ENTROPY,
                details={"distribution": metrics.bandit_selection_distribution}
            )
        
        # 3. KPI variance explosion
        if metrics.kpi_variance > self.MAX_KPI_VARIANCE:
            return HardStopEvent(
                timestamp=datetime.now().isoformat(),
                reason="kpi_variance_explosion",
                metric_name="kpi_variance",
                metric_value=metrics.kpi_variance,
                threshold=self.MAX_KPI_VARIANCE,
                details={"buffer_size": len(self.kpi_buffer)}
            )
        
        # 4. Bandit collapse to single strategy
        if tick > 20:
            max_ratio = max(metrics.bandit_selection_distribution.values()) if metrics.bandit_selection_distribution else 0
            if max_ratio > (1 - self.MIN_BANDIT_DIVERSITY):
                dominant = max(metrics.bandit_selection_distribution, key=metrics.bandit_selection_distribution.get)
                return HardStopEvent(
                    timestamp=datetime.now().isoformat(),
                    reason="bandit_collapse_to_single_strategy",
                    metric_name="max_selection_ratio",
                    metric_value=max_ratio,
                    threshold=1 - self.MIN_BANDIT_DIVERSITY,
                    details={"dominant_policy": dominant}
                )
        
        # 5. Failure budget exceeded
        budget_ratio = self.failure_budget_spent / self.failure_budget_total
        if budget_ratio > self.MAX_FAILURE_BUDGET_SPENT:
            return HardStopEvent(
                timestamp=datetime.now().isoformat(),
                reason="failure_budget_exceeded",
                metric_name="budget_spent_ratio",
                metric_value=budget_ratio,
                threshold=self.MAX_FAILURE_BUDGET_SPENT,
                details={"spent": self.failure_budget_spent, "total": self.failure_budget_total}
            )
        
        return None
    
    def _save_artifacts(self) -> None:
        """Save all artifacts."""
        exploration_dir = os.path.join(self.artifacts_dir, "exploration")
        os.makedirs(exploration_dir, exist_ok=True)
        
        # Stability metrics
        metrics_path = os.path.join(exploration_dir, "stability_metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "1.0",
                "metrics": [m.to_dict() for m in self.metrics_history],
                "generated_at": datetime.now().isoformat()
            }, f, indent=2)
        
        # Hard stop event (if any)
        if self.hard_stop_event:
            stop_path = os.path.join(exploration_dir, "hard_stop_event.json")
            with open(stop_path, "w", encoding="utf-8") as f:
                json.dump(self.hard_stop_event.to_dict(), f, indent=2)
        
        print(f"[Shadow Evolution] Saved artifacts to {exploration_dir}")
    
    def _generate_summary(self, start_time: datetime) -> Dict[str, Any]:
        """Generate run summary."""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        final_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        return {
            "status": "hard_stopped" if self.hard_stop_event else "completed",
            "duration_seconds": duration,
            "total_ticks": len(self.metrics_history),
            "final_candidate_count": len(self.candidate_policies),
            "final_entropy": final_metrics.strategy_entropy if final_metrics else 0.0,
            "final_kpi_variance": final_metrics.kpi_variance if final_metrics else 0.0,
            "hard_stop": self.hard_stop_event.to_dict() if self.hard_stop_event else None,
            "artifacts_dir": self.artifacts_dir
        }


def main():
    parser = argparse.ArgumentParser(description="Shadow Evolution Burn-in Runner")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    parser.add_argument("--candidates", type=int, default=3, help="Initial candidate count")
    parser.add_argument("--tick-interval", type=float, default=0.1, help="Tick interval in seconds")
    parser.add_argument("--artifacts-dir", type=str, default="artifacts", help="Artifacts directory")
    
    args = parser.parse_args()
    
    runner = ShadowEvolutionRunner(
        artifacts_dir=args.artifacts_dir,
        num_candidates=args.candidates
    )
    
    summary = runner.run(
        duration_seconds=args.duration,
        tick_interval=args.tick_interval
    )
    
    print("\n" + "=" * 50)
    print("Shadow Evolution Summary")
    print("=" * 50)
    print(json.dumps(summary, indent=2))
    
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())



