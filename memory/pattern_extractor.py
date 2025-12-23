"""
Pattern Extractor - Extract patterns from historical runs
L5 Core Component: Cross-run experience abstraction
"""

from typing import List, Dict, Any, Set, Optional
from collections import defaultdict, Counter
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class ExtractedPattern(dict):
    """Extracted pattern from multiple runs"""
    pass


class PatternExtractor:
    """
    Extracts reusable patterns from historical execution data
    Enables learning from past runs
    """
    
    def __init__(
        self,
        artifacts_path: str = "artifacts",
        memory_path: str = "memory/extracted_patterns"
    ):
        self.artifacts_path = Path(artifacts_path)
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
    
    def extract_from_recent_runs(self, window_days: int = 7, min_runs: int = 5) -> List[ExtractedPattern]:
        """
        Extract patterns from recent runs
        Args:
            window_days: Time window to consider
            min_runs: Minimum runs needed to form a pattern
        """
        patterns = []
        
        # 1. Collect recent run data
        recent_runs = self._load_recent_runs(window_days)
        
        if len(recent_runs) < min_runs:
            print(f"⚠️ Only {len(recent_runs)} runs found, need at least {min_runs}")
            return patterns
        
        # 2. Extract different types of patterns
        patterns.extend(self._extract_goal_patterns(recent_runs))
        patterns.extend(self._extract_tool_sequence_patterns(recent_runs))
        patterns.extend(self._extract_success_failure_patterns(recent_runs))
        patterns.extend(self._extract_cost_optimization_patterns(recent_runs))
        
        # 3. Persist patterns
        self._save_patterns(patterns)
        
        return patterns
    
    def _load_recent_runs(self, window_days: int) -> List[Dict[str, Any]]:
        """Load recent run data from artifacts"""
        cutoff_time = datetime.now() - timedelta(days=window_days)
        recent_runs = []
        
        # Load from eval artifacts
        eval_dir = self.artifacts_path / "eval"
        if eval_dir.exists():
            for file in eval_dir.glob("*.json"):
                try:
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if mtime >= cutoff_time:
                        with open(file) as f:
                            run_data = json.load(f)
                            run_data["run_id"] = file.stem
                            
                            # Enrich with goal data if available
                            goal_file = self.artifacts_path / "goals" / f"{file.stem}_goal_interpretation.json"
                            if goal_file.exists():
                                with open(goal_file) as gf:
                                    run_data["goal"] = json.load(gf)
                            
                            recent_runs.append(run_data)
                except Exception as e:
                    print(f"Warning: Could not load {file}: {e}")
                    continue
        
        return recent_runs
    
    def _extract_goal_patterns(self, runs: List[Dict[str, Any]]) -> List[ExtractedPattern]:
        """Extract patterns based on goal types"""
        patterns = []
        
        # Group by goal type
        by_goal_type = defaultdict(list)
        for run in runs:
            if "goal" in run:
                goal_type = run["goal"].get("goal_type", "unknown")
                by_goal_type[goal_type].append(run)
        
        # Analyze each goal type
        for goal_type, type_runs in by_goal_type.items():
            if len(type_runs) < 3:
                continue
            
            successes = [r for r in type_runs if r.get("success", False)]
            success_rate = len(successes) / len(type_runs)
            avg_quality = sum(r.get("quality_score", 0) for r in successes) / len(successes) if successes else 0
            avg_cost = sum(r.get("cost", 0) for r in type_runs) / len(type_runs)
            
            pattern = ExtractedPattern({
                "pattern_type": "goal_performance",
                "goal_type": goal_type,
                "sample_size": len(type_runs),
                "success_rate": success_rate,
                "avg_quality": avg_quality,
                "avg_cost": avg_cost,
                "confidence": min(1.0, len(type_runs) / 10),  # Higher confidence with more samples
                "extracted_at": datetime.now().isoformat()
            })
            
            patterns.append(pattern)
        
        return patterns
    
    def _extract_tool_sequence_patterns(self, runs: List[Dict[str, Any]]) -> List[ExtractedPattern]:
        """Extract patterns based on tool usage sequences"""
        patterns = []
        
        # This would require tool usage tracking from runs
        # For now, create a placeholder pattern
        tool_usage = defaultdict(int)
        
        # Simulate tool extraction (in real system, this would come from execution traces)
        for run in runs:
            # Placeholder: extract from task_type as proxy
            task_type = run.get("task_type", "unknown")
            if task_type == "rag_qa":
                tool_usage["retriever"] += 1
                tool_usage["llm_generator"] += 1
        
        if tool_usage:
            pattern = ExtractedPattern({
                "pattern_type": "tool_usage_frequency",
                "tool_counts": dict(tool_usage),
                "most_common_tools": [tool for tool, _ in Counter(tool_usage).most_common(5)],
                "extracted_at": datetime.now().isoformat()
            })
            patterns.append(pattern)
        
        return patterns
    
    def _extract_success_failure_patterns(self, runs: List[Dict[str, Any]]) -> List[ExtractedPattern]:
        """Extract patterns distinguishing success from failure"""
        patterns = []
        
        successes = [r for r in runs if r.get("success", False)]
        failures = [r for r in runs if not r.get("success", False)]
        
        if successes and failures:
            # Compare characteristics
            success_avg_latency = sum(r.get("latency", 0) for r in successes) / len(successes)
            failure_avg_latency = sum(r.get("latency", 0) for r in failures) / len(failures) if failures else 0
            
            pattern = ExtractedPattern({
                "pattern_type": "success_failure_analysis",
                "total_runs": len(runs),
                "success_count": len(successes),
                "failure_count": len(failures),
                "success_characteristics": {
                    "avg_latency_ms": success_avg_latency,
                    "common_task_types": self._get_common_values(successes, "task_type")
                },
                "failure_characteristics": {
                    "avg_latency_ms": failure_avg_latency,
                    "common_task_types": self._get_common_values(failures, "task_type")
                },
                "extracted_at": datetime.now().isoformat()
            })
            
            patterns.append(pattern)
        
        return patterns
    
    def _extract_cost_optimization_patterns(self, runs: List[Dict[str, Any]]) -> List[ExtractedPattern]:
        """Extract patterns for cost optimization"""
        patterns = []
        
        if not runs:
            return patterns
        
        # Find cost-effective runs (high quality, low cost)
        quality_cost_runs = [
            (r.get("quality_score", 0), r.get("cost", 0), r.get("task_type", "unknown"))
            for r in runs
            if r.get("quality_score", 0) > 0
        ]
        
        if quality_cost_runs:
            # Calculate efficiency score: quality / cost
            efficient_runs = [
                (q / c if c > 0 else 0, task_type)
                for q, c, task_type in quality_cost_runs
            ]
            
            avg_efficiency = sum(e for e, _ in efficient_runs) / len(efficient_runs)
            
            # Group by task type
            efficiency_by_type = defaultdict(list)
            for efficiency, task_type in efficient_runs:
                efficiency_by_type[task_type].append(efficiency)
            
            best_task_type = max(
                efficiency_by_type.items(),
                key=lambda x: sum(x[1]) / len(x[1])
            )[0] if efficiency_by_type else "unknown"
            
            pattern = ExtractedPattern({
                "pattern_type": "cost_optimization",
                "avg_efficiency_score": avg_efficiency,
                "most_efficient_task_type": best_task_type,
                "sample_size": len(quality_cost_runs),
                "recommendation": f"Focus on {best_task_type} tasks for best cost/quality ratio",
                "extracted_at": datetime.now().isoformat()
            })
            
            patterns.append(pattern)
        
        return patterns
    
    def _get_common_values(self, runs: List[Dict[str, Any]], key: str, top_k: int = 3) -> List[str]:
        """Get most common values for a key across runs"""
        values = [r.get(key) for r in runs if key in r]
        return [val for val, _ in Counter(values).most_common(top_k)]
    
    def _save_patterns(self, patterns: List[ExtractedPattern]):
        """Save extracted patterns to disk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.memory_path / f"patterns_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(patterns, f, indent=2, default=str)
        
        # Also maintain a "latest" symlink/copy
        latest_file = self.memory_path / "patterns_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(patterns, f, indent=2, default=str)
    
    def get_latest_patterns(self) -> List[ExtractedPattern]:
        """Load most recent extracted patterns"""
        latest_file = self.memory_path / "patterns_latest.json"
        
        if latest_file.exists():
            with open(latest_file) as f:
                return json.load(f)
        
        return []
    
    def get_recommendation_for_goal(self, goal_type: str) -> Optional[Dict[str, Any]]:
        """Get recommendation based on extracted patterns"""
        patterns = self.get_latest_patterns()
        
        # Find relevant patterns
        relevant = [
            p for p in patterns
            if p.get("pattern_type") == "goal_performance" and p.get("goal_type") == goal_type
        ]
        
        if relevant:
            best = max(relevant, key=lambda p: p.get("success_rate", 0))
            return {
                "goal_type": goal_type,
                "expected_success_rate": best.get("success_rate"),
                "expected_cost": best.get("avg_cost"),
                "confidence": best.get("confidence"),
                "based_on_runs": best.get("sample_size")
            }
        
        return None


# Singleton instance
_extractor = None

def get_pattern_extractor() -> PatternExtractor:
    """Get singleton PatternExtractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = PatternExtractor()
    return _extractor



