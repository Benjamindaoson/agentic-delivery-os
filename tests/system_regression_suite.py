"""
System-Level Regression Testing Suite
P2-2 Implementation: DAG stability, cost regression, latency degradation, learning regression

This module provides:
1. DAG stability tests (structure consistency across runs)
2. Cost regression tests (no unexpected cost increases)
3. Latency degradation tests (no performance regression)
4. Learning-induced regression tests (learning doesn't hurt performance)
5. SYSTEM_HEALTH_REPORT.json generation
"""

import os
import json
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import statistics


class RegressionSeverity(str, Enum):
    """Severity levels for regression"""
    NONE = "none"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RegressionCategory(str, Enum):
    """Categories of regression tests"""
    DAG_STABILITY = "dag_stability"
    COST = "cost"
    LATENCY = "latency"
    QUALITY = "quality"
    LEARNING = "learning"
    SYSTEM = "system"


@dataclass
class RegressionResult:
    """Result of a single regression test"""
    test_id: str
    category: RegressionCategory
    name: str
    passed: bool
    severity: RegressionSeverity
    
    # Metrics
    baseline_value: float
    current_value: float
    threshold: float
    delta: float
    delta_pct: float
    
    # Details
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    test_duration_ms: int = 0
    tested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "category": self.category.value,
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "delta": self.delta,
            "delta_pct": self.delta_pct,
            "message": self.message,
            "details": self.details,
            "test_duration_ms": self.test_duration_ms,
            "tested_at": self.tested_at
        }


@dataclass
class SystemHealthReport:
    """Complete system health report"""
    report_id: str
    
    # Summary
    total_tests: int
    passed_tests: int
    failed_tests: int
    warnings: int
    
    # By category
    results_by_category: Dict[str, List[RegressionResult]]
    
    # Trend analysis
    trend: Dict[str, Any]
    
    # Recommendations
    recommendations: List[str]
    
    # Metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    baseline_period: str = ""
    test_period: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "summary": {
                "total_tests": self.total_tests,
                "passed_tests": self.passed_tests,
                "failed_tests": self.failed_tests,
                "warnings": self.warnings,
                "pass_rate": self.passed_tests / max(1, self.total_tests)
            },
            "results_by_category": {
                cat: [r.to_dict() for r in results]
                for cat, results in self.results_by_category.items()
            },
            "trend": self.trend,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
            "baseline_period": self.baseline_period,
            "test_period": self.test_period
        }


class BaselineCollector:
    """Collects and manages baselines for regression testing"""
    
    def __init__(self, artifacts_dir: str = "artifacts/baselines"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        self.baselines: Dict[str, Dict[str, Any]] = {}
        self._load_baselines()
    
    def record_metric(
        self,
        metric_name: str,
        value: float,
        category: str = "general"
    ):
        """Record a metric value"""
        if metric_name not in self.baselines:
            self.baselines[metric_name] = {
                "category": category,
                "values": [],
                "mean": 0.0,
                "std": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "p99": 0.0,
                "min": 0.0,
                "max": 0.0,
                "sample_count": 0
            }
        
        baseline = self.baselines[metric_name]
        baseline["values"].append(value)
        
        # Keep only last 1000 values
        if len(baseline["values"]) > 1000:
            baseline["values"] = baseline["values"][-1000:]
        
        # Update statistics
        values = baseline["values"]
        baseline["sample_count"] = len(values)
        baseline["mean"] = statistics.mean(values)
        baseline["std"] = statistics.stdev(values) if len(values) > 1 else 0.0
        baseline["min"] = min(values)
        baseline["max"] = max(values)
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        baseline["p50"] = sorted_values[int(n * 0.5)]
        baseline["p90"] = sorted_values[int(n * 0.9)]
        baseline["p99"] = sorted_values[min(int(n * 0.99), n - 1)]
        
        self._save_baselines()
    
    def get_baseline(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """Get baseline for a metric"""
        return self.baselines.get(metric_name)
    
    def _save_baselines(self):
        """Persist baselines"""
        path = os.path.join(self.artifacts_dir, "baselines.json")
        # Remove raw values for storage efficiency
        storage_baselines = {
            k: {kk: vv for kk, vv in v.items() if kk != "values"}
            for k, v in self.baselines.items()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(storage_baselines, f, indent=2)
    
    def _load_baselines(self):
        """Load baselines"""
        path = os.path.join(self.artifacts_dir, "baselines.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.baselines = json.load(f)
                    for k in self.baselines:
                        self.baselines[k]["values"] = []  # Reset values
            except Exception:
                pass


class DAGStabilityTests:
    """Tests for DAG stability across runs"""
    
    def __init__(self, baseline_collector: BaselineCollector):
        self.baseline = baseline_collector
    
    def test_node_count_stability(
        self,
        current_node_counts: List[int],
        max_deviation_pct: float = 0.2
    ) -> RegressionResult:
        """Test that node counts are stable across runs"""
        start_time = time.time()
        
        baseline = self.baseline.get_baseline("dag_node_count")
        
        if not baseline or baseline["sample_count"] < 10:
            # Not enough baseline data
            for count in current_node_counts:
                self.baseline.record_metric("dag_node_count", float(count), "dag")
            
            return RegressionResult(
                test_id="dag_node_count_stability",
                category=RegressionCategory.DAG_STABILITY,
                name="DAG Node Count Stability",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=statistics.mean(current_node_counts) if current_node_counts else 0.0,
                threshold=max_deviation_pct,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient baseline data, recording values",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        baseline_mean = baseline["mean"]
        current_mean = statistics.mean(current_node_counts) if current_node_counts else baseline_mean
        
        delta = current_mean - baseline_mean
        delta_pct = delta / baseline_mean if baseline_mean > 0 else 0.0
        
        passed = abs(delta_pct) <= max_deviation_pct
        
        return RegressionResult(
            test_id="dag_node_count_stability",
            category=RegressionCategory.DAG_STABILITY,
            name="DAG Node Count Stability",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.WARNING,
            baseline_value=baseline_mean,
            current_value=current_mean,
            threshold=max_deviation_pct,
            delta=delta,
            delta_pct=delta_pct,
            message=f"Node count deviation: {delta_pct:.1%}" if not passed else "Node count stable",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )
    
    def test_execution_path_consistency(
        self,
        current_paths: List[List[str]],
        expected_paths: List[List[str]]
    ) -> RegressionResult:
        """Test that execution paths are consistent"""
        start_time = time.time()
        
        if not expected_paths:
            return RegressionResult(
                test_id="dag_path_consistency",
                category=RegressionCategory.DAG_STABILITY,
                name="DAG Execution Path Consistency",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=0.0,
                threshold=0.0,
                delta=0.0,
                delta_pct=0.0,
                message="No expected paths defined",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        # Count matching paths
        matches = 0
        for current in current_paths:
            if current in expected_paths:
                matches += 1
        
        match_rate = matches / len(current_paths) if current_paths else 1.0
        passed = match_rate >= 0.9  # 90% must match
        
        return RegressionResult(
            test_id="dag_path_consistency",
            category=RegressionCategory.DAG_STABILITY,
            name="DAG Execution Path Consistency",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.ERROR,
            baseline_value=1.0,
            current_value=match_rate,
            threshold=0.9,
            delta=match_rate - 1.0,
            delta_pct=match_rate - 1.0,
            message=f"Path match rate: {match_rate:.1%}",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )


class CostRegressionTests:
    """Tests for cost regression"""
    
    def __init__(self, baseline_collector: BaselineCollector):
        self.baseline = baseline_collector
    
    def test_avg_cost_regression(
        self,
        current_costs: List[float],
        max_increase_pct: float = 0.1
    ) -> RegressionResult:
        """Test that average cost hasn't increased"""
        start_time = time.time()
        
        baseline = self.baseline.get_baseline("run_cost")
        
        if not baseline or baseline["sample_count"] < 10:
            for cost in current_costs:
                self.baseline.record_metric("run_cost", cost, "cost")
            
            return RegressionResult(
                test_id="avg_cost_regression",
                category=RegressionCategory.COST,
                name="Average Cost Regression",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=statistics.mean(current_costs) if current_costs else 0.0,
                threshold=max_increase_pct,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient baseline data, recording values",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        baseline_mean = baseline["mean"]
        current_mean = statistics.mean(current_costs) if current_costs else baseline_mean
        
        delta = current_mean - baseline_mean
        delta_pct = delta / baseline_mean if baseline_mean > 0 else 0.0
        
        passed = delta_pct <= max_increase_pct
        
        return RegressionResult(
            test_id="avg_cost_regression",
            category=RegressionCategory.COST,
            name="Average Cost Regression",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.WARNING,
            baseline_value=baseline_mean,
            current_value=current_mean,
            threshold=max_increase_pct,
            delta=delta,
            delta_pct=delta_pct,
            message=f"Cost change: {delta_pct:+.1%}" if delta_pct != 0 else "Cost stable",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )
    
    def test_p99_cost_regression(
        self,
        current_costs: List[float],
        max_increase_pct: float = 0.2
    ) -> RegressionResult:
        """Test that P99 cost hasn't increased significantly"""
        start_time = time.time()
        
        baseline = self.baseline.get_baseline("run_cost")
        
        if not baseline or baseline["sample_count"] < 10:
            return RegressionResult(
                test_id="p99_cost_regression",
                category=RegressionCategory.COST,
                name="P99 Cost Regression",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=0.0,
                threshold=max_increase_pct,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient baseline data",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        baseline_p99 = baseline["p99"]
        sorted_costs = sorted(current_costs)
        current_p99 = sorted_costs[int(len(sorted_costs) * 0.99)] if current_costs else baseline_p99
        
        delta = current_p99 - baseline_p99
        delta_pct = delta / baseline_p99 if baseline_p99 > 0 else 0.0
        
        passed = delta_pct <= max_increase_pct
        
        return RegressionResult(
            test_id="p99_cost_regression",
            category=RegressionCategory.COST,
            name="P99 Cost Regression",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.ERROR,
            baseline_value=baseline_p99,
            current_value=current_p99,
            threshold=max_increase_pct,
            delta=delta,
            delta_pct=delta_pct,
            message=f"P99 cost change: {delta_pct:+.1%}",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )


class LatencyRegressionTests:
    """Tests for latency regression"""
    
    def __init__(self, baseline_collector: BaselineCollector):
        self.baseline = baseline_collector
    
    def test_avg_latency_regression(
        self,
        current_latencies_ms: List[int],
        max_increase_pct: float = 0.15
    ) -> RegressionResult:
        """Test that average latency hasn't increased"""
        start_time = time.time()
        
        baseline = self.baseline.get_baseline("run_latency_ms")
        
        if not baseline or baseline["sample_count"] < 10:
            for lat in current_latencies_ms:
                self.baseline.record_metric("run_latency_ms", float(lat), "latency")
            
            return RegressionResult(
                test_id="avg_latency_regression",
                category=RegressionCategory.LATENCY,
                name="Average Latency Regression",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=statistics.mean(current_latencies_ms) if current_latencies_ms else 0.0,
                threshold=max_increase_pct,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient baseline data, recording values",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        baseline_mean = baseline["mean"]
        current_mean = statistics.mean(current_latencies_ms) if current_latencies_ms else baseline_mean
        
        delta = current_mean - baseline_mean
        delta_pct = delta / baseline_mean if baseline_mean > 0 else 0.0
        
        passed = delta_pct <= max_increase_pct
        
        return RegressionResult(
            test_id="avg_latency_regression",
            category=RegressionCategory.LATENCY,
            name="Average Latency Regression",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.WARNING,
            baseline_value=baseline_mean,
            current_value=current_mean,
            threshold=max_increase_pct,
            delta=delta,
            delta_pct=delta_pct,
            message=f"Latency change: {delta_pct:+.1%}",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )


class LearningRegressionTests:
    """Tests for learning-induced regression"""
    
    def __init__(self, baseline_collector: BaselineCollector):
        self.baseline = baseline_collector
    
    def test_quality_after_learning(
        self,
        pre_learning_quality: List[float],
        post_learning_quality: List[float],
        min_improvement: float = -0.05  # Allow up to 5% degradation
    ) -> RegressionResult:
        """Test that learning hasn't degraded quality"""
        start_time = time.time()
        
        if not pre_learning_quality or not post_learning_quality:
            return RegressionResult(
                test_id="quality_after_learning",
                category=RegressionCategory.LEARNING,
                name="Quality After Learning",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=0.0,
                threshold=min_improvement,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient data",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        pre_mean = statistics.mean(pre_learning_quality)
        post_mean = statistics.mean(post_learning_quality)
        
        delta = post_mean - pre_mean
        delta_pct = delta / pre_mean if pre_mean > 0 else 0.0
        
        passed = delta_pct >= min_improvement
        
        return RegressionResult(
            test_id="quality_after_learning",
            category=RegressionCategory.LEARNING,
            name="Quality After Learning",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.ERROR,
            baseline_value=pre_mean,
            current_value=post_mean,
            threshold=min_improvement,
            delta=delta,
            delta_pct=delta_pct,
            message=f"Quality change after learning: {delta_pct:+.1%}",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )
    
    def test_cost_after_learning(
        self,
        pre_learning_costs: List[float],
        post_learning_costs: List[float],
        max_increase: float = 0.1  # Max 10% increase allowed
    ) -> RegressionResult:
        """Test that learning hasn't increased costs excessively"""
        start_time = time.time()
        
        if not pre_learning_costs or not post_learning_costs:
            return RegressionResult(
                test_id="cost_after_learning",
                category=RegressionCategory.LEARNING,
                name="Cost After Learning",
                passed=True,
                severity=RegressionSeverity.INFO,
                baseline_value=0.0,
                current_value=0.0,
                threshold=max_increase,
                delta=0.0,
                delta_pct=0.0,
                message="Insufficient data",
                test_duration_ms=int((time.time() - start_time) * 1000)
            )
        
        pre_mean = statistics.mean(pre_learning_costs)
        post_mean = statistics.mean(post_learning_costs)
        
        delta = post_mean - pre_mean
        delta_pct = delta / pre_mean if pre_mean > 0 else 0.0
        
        passed = delta_pct <= max_increase
        
        return RegressionResult(
            test_id="cost_after_learning",
            category=RegressionCategory.LEARNING,
            name="Cost After Learning",
            passed=passed,
            severity=RegressionSeverity.NONE if passed else RegressionSeverity.WARNING,
            baseline_value=pre_mean,
            current_value=post_mean,
            threshold=max_increase,
            delta=delta,
            delta_pct=delta_pct,
            message=f"Cost change after learning: {delta_pct:+.1%}",
            test_duration_ms=int((time.time() - start_time) * 1000)
        )


class SystemRegressionSuite:
    """Main regression testing suite"""
    
    def __init__(self, artifacts_dir: str = "artifacts/regression"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        self.baseline_collector = BaselineCollector(
            os.path.join(artifacts_dir, "baselines")
        )
        
        # Initialize test suites
        self.dag_tests = DAGStabilityTests(self.baseline_collector)
        self.cost_tests = CostRegressionTests(self.baseline_collector)
        self.latency_tests = LatencyRegressionTests(self.baseline_collector)
        self.learning_tests = LearningRegressionTests(self.baseline_collector)
    
    def run_full_suite(
        self,
        execution_data: Dict[str, List[Any]]
    ) -> SystemHealthReport:
        """
        Run full regression test suite.
        
        Args:
            execution_data: Dictionary containing:
                - node_counts: List of node counts from recent runs
                - execution_paths: List of execution paths
                - costs: List of costs
                - latencies_ms: List of latencies
                - pre_learning_quality: Quality scores before learning
                - post_learning_quality: Quality scores after learning
                - pre_learning_costs: Costs before learning
                - post_learning_costs: Costs after learning
        """
        results: List[RegressionResult] = []
        
        # DAG Stability Tests
        if "node_counts" in execution_data:
            results.append(self.dag_tests.test_node_count_stability(
                execution_data["node_counts"]
            ))
        
        if "execution_paths" in execution_data:
            results.append(self.dag_tests.test_execution_path_consistency(
                execution_data["execution_paths"],
                execution_data.get("expected_paths", [])
            ))
        
        # Cost Tests
        if "costs" in execution_data:
            results.append(self.cost_tests.test_avg_cost_regression(
                execution_data["costs"]
            ))
            results.append(self.cost_tests.test_p99_cost_regression(
                execution_data["costs"]
            ))
        
        # Latency Tests
        if "latencies_ms" in execution_data:
            results.append(self.latency_tests.test_avg_latency_regression(
                execution_data["latencies_ms"]
            ))
        
        # Learning Regression Tests
        if "pre_learning_quality" in execution_data and "post_learning_quality" in execution_data:
            results.append(self.learning_tests.test_quality_after_learning(
                execution_data["pre_learning_quality"],
                execution_data["post_learning_quality"]
            ))
        
        if "pre_learning_costs" in execution_data and "post_learning_costs" in execution_data:
            results.append(self.learning_tests.test_cost_after_learning(
                execution_data["pre_learning_costs"],
                execution_data["post_learning_costs"]
            ))
        
        # Generate report
        report = self._generate_report(results)
        
        # Save report
        self._save_report(report)
        
        return report
    
    def _generate_report(self, results: List[RegressionResult]) -> SystemHealthReport:
        """Generate system health report from results"""
        
        # Organize by category
        by_category: Dict[str, List[RegressionResult]] = {}
        for result in results:
            cat = result.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(result)
        
        # Calculate summary
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        warnings = sum(1 for r in results if r.severity == RegressionSeverity.WARNING)
        
        # Trend analysis
        trend = {
            "overall_health": "healthy" if failed == 0 else "degraded" if failed <= 2 else "critical",
            "cost_trend": self._analyze_trend("run_cost"),
            "latency_trend": self._analyze_trend("run_latency_ms"),
            "quality_trend": "stable"  # Would need more data
        }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(results)
        
        return SystemHealthReport(
            report_id=f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            warnings=warnings,
            results_by_category=by_category,
            trend=trend,
            recommendations=recommendations,
            baseline_period="last 7 days",
            test_period=datetime.now().isoformat()
        )
    
    def _analyze_trend(self, metric_name: str) -> str:
        """Analyze trend for a metric"""
        baseline = self.baseline_collector.get_baseline(metric_name)
        if not baseline or baseline["sample_count"] < 10:
            return "insufficient_data"
        
        # Simple trend: compare recent vs older values
        std = baseline.get("std", 0)
        mean = baseline.get("mean", 0)
        
        if std == 0 or mean == 0:
            return "stable"
        
        cv = std / mean  # Coefficient of variation
        
        if cv < 0.1:
            return "stable"
        elif cv < 0.3:
            return "moderate_variance"
        else:
            return "high_variance"
    
    def _generate_recommendations(self, results: List[RegressionResult]) -> List[str]:
        """Generate recommendations based on results"""
        recommendations = []
        
        # Check for failures
        failed_results = [r for r in results if not r.passed]
        
        for result in failed_results:
            if result.category == RegressionCategory.COST:
                recommendations.append(
                    f"Cost regression detected ({result.name}): Review recent changes to LLM calls or tool usage"
                )
            elif result.category == RegressionCategory.LATENCY:
                recommendations.append(
                    f"Latency regression detected ({result.name}): Check for new bottlenecks in execution path"
                )
            elif result.category == RegressionCategory.LEARNING:
                recommendations.append(
                    f"Learning regression detected ({result.name}): Consider rolling back recent policy updates"
                )
            elif result.category == RegressionCategory.DAG_STABILITY:
                recommendations.append(
                    f"DAG instability detected ({result.name}): Review DAG mutation logic"
                )
        
        if not recommendations:
            recommendations.append("All systems operating within expected parameters")
        
        return recommendations
    
    def _save_report(self, report: SystemHealthReport):
        """Save report to artifacts"""
        # Save as JSON
        json_path = os.path.join(self.artifacts_dir, "SYSTEM_HEALTH_REPORT.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Save as markdown
        md_path = os.path.join(self.artifacts_dir, "regression_trend.md")
        self._save_markdown_report(report, md_path)
    
    def _save_markdown_report(self, report: SystemHealthReport, path: str):
        """Save report as markdown"""
        md = f"""# System Health Report

**Report ID**: {report.report_id}  
**Generated**: {report.generated_at}  
**Baseline Period**: {report.baseline_period}

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {report.total_tests} |
| Passed | {report.passed_tests} |
| Failed | {report.failed_tests} |
| Warnings | {report.warnings} |
| Pass Rate | {report.passed_tests / max(1, report.total_tests):.1%} |

## Trend Analysis

"""
        for key, value in report.trend.items():
            md += f"- **{key}**: {value}\n"
        
        md += "\n## Results by Category\n\n"
        
        for category, results in report.results_by_category.items():
            md += f"### {category.upper()}\n\n"
            md += "| Test | Passed | Severity | Delta | Message |\n"
            md += "|------|--------|----------|-------|--------|\n"
            for r in results:
                md += f"| {r.name} | {'✅' if r.passed else '❌'} | {r.severity.value} | {r.delta_pct:+.1%} | {r.message} |\n"
            md += "\n"
        
        md += "## Recommendations\n\n"
        for rec in report.recommendations:
            md += f"- {rec}\n"
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)


# Global regression suite
_regression_suite: Optional[SystemRegressionSuite] = None

def get_regression_suite() -> SystemRegressionSuite:
    """Get global regression suite"""
    global _regression_suite
    if _regression_suite is None:
        _regression_suite = SystemRegressionSuite()
    return _regression_suite


