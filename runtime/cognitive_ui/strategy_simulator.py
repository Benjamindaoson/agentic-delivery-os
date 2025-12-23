"""
Strategy Simulator - "What if" analysis for strategies
L6 Component: Cognitive UI - Strategy Playground
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os


class StrategySimulator:
    """
    Simulates strategy performance based on historical data
    Enables "what if" analysis before deployment
    """
    
    def __init__(self, artifacts_path: str = "artifacts/simulations"):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
    
    def simulate_strategy(
        self,
        strategy_config: Dict[str, Any],
        historical_runs: List[Dict[str, Any]],
        num_simulations: int = 100
    ) -> Dict[str, Any]:
        """
        Simulate strategy on historical data
        Returns: predicted performance metrics
        """
        # Extract strategy components
        planner_strategy = strategy_config.get("planner_strategy", "sequential")
        tool_preferences = strategy_config.get("tool_preferences", {})
        cost_tolerance = strategy_config.get("cost_tolerance", 1.0)
        quality_threshold = strategy_config.get("quality_threshold", 0.7)
        
        # Simulate on historical runs
        successes = 0
        total_cost = 0.0
        total_latency = 0.0
        quality_scores = []
        
        for run in historical_runs[:num_simulations]:
            # Simple heuristic simulation
            goal_type = run.get("goal_type", "unknown")
            
            # Strategy affinity (simplified)
            if planner_strategy == "parallel" and goal_type in ["analyze", "compare"]:
                success_prob = 0.85
            elif planner_strategy == "sequential" and goal_type in ["retrieve", "qa"]:
                success_prob = 0.80
            elif planner_strategy == "hierarchical":
                success_prob = 0.75
            else:
                success_prob = 0.70
            
            # Cost estimation
            estimated_cost = run.get("actual_cost", 0.05) * cost_tolerance
            estimated_latency = run.get("actual_latency", 1000)
            estimated_quality = success_prob + (0.1 if tool_preferences.get("retriever", 1.0) > 0.8 else 0)
            
            # Simulate success
            import random
            if random.random() < success_prob and estimated_quality >= quality_threshold:
                successes += 1
                quality_scores.append(estimated_quality)
            
            total_cost += estimated_cost
            total_latency += estimated_latency
        
        # Compute metrics
        n = len(historical_runs[:num_simulations])
        result = {
            "strategy_config": strategy_config,
            "num_simulations": n,
            "predicted_metrics": {
                "success_rate": successes / n if n > 0 else 0,
                "avg_cost": total_cost / n if n > 0 else 0,
                "avg_latency_ms": total_latency / n if n > 0 else 0,
                "avg_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                "cost_efficiency": (successes / total_cost) if total_cost > 0 else 0
            },
            "confidence": 0.7,  # Based on simulation quality
            "simulated_at": datetime.now().isoformat()
        }
        
        # Save simulation
        self._save_simulation(result)
        
        return result
    
    def compare_strategies(
        self,
        strategies: List[Dict[str, Any]],
        historical_runs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare multiple strategies
        Returns: comparative analysis
        """
        results = []
        
        for strategy in strategies:
            result = self.simulate_strategy(strategy, historical_runs)
            results.append(result)
        
        # Rank by success rate
        ranked = sorted(results, key=lambda x: x["predicted_metrics"]["success_rate"], reverse=True)
        
        return {
            "strategies_compared": len(strategies),
            "results": ranked,
            "best_strategy": ranked[0]["strategy_config"] if ranked else None,
            "comparison_at": datetime.now().isoformat()
        }
    
    def counterfactual_analysis(
        self,
        actual_run: Dict[str, Any],
        alternative_strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        "What if we had used a different strategy?"
        """
        actual_success = actual_run.get("success", False)
        actual_cost = actual_run.get("cost", 0)
        actual_quality = actual_run.get("quality_score", 0)
        
        # Simulate alternative
        alt_result = self.simulate_strategy(alternative_strategy, [actual_run], num_simulations=1)
        alt_metrics = alt_result["predicted_metrics"]
        
        return {
            "run_id": actual_run.get("run_id"),
            "actual": {
                "success": actual_success,
                "cost": actual_cost,
                "quality": actual_quality
            },
            "counterfactual": {
                "strategy": alternative_strategy,
                "predicted_success_rate": alt_metrics["success_rate"],
                "predicted_cost": alt_metrics["avg_cost"],
                "predicted_quality": alt_metrics["avg_quality"]
            },
            "delta": {
                "cost_savings": actual_cost - alt_metrics["avg_cost"],
                "quality_improvement": alt_metrics["avg_quality"] - actual_quality,
                "would_have_succeeded": alt_metrics["success_rate"] > 0.5 and not actual_success
            }
        }
    
    def _save_simulation(self, result: Dict[str, Any]):
        """Save simulation result"""
        import uuid
        sim_id = f"sim_{uuid.uuid4().hex[:8]}"
        path = os.path.join(self.artifacts_path, f"{sim_id}.json")
        with open(path, 'w') as f:
            json.dump(result, f, indent=2)


# Global simulator
_simulator: Optional[StrategySimulator] = None

def get_strategy_simulator() -> StrategySimulator:
    """Get global strategy simulator"""
    global _simulator
    if _simulator is None:
        _simulator = StrategySimulator()
    return _simulator



