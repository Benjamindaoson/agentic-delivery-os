"""
Benchmark Runner - Offline benchmark execution and comparison
L5 Core Component: Systematic evaluation
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
from pathlib import Path


class BenchmarkTask(BaseModel):
    """Single benchmark task"""
    task_id: str
    query: str
    expected_output: Optional[str] = None
    expected_quality_min: float = 0.7
    max_cost: float = 1.0
    task_type: str


class BenchmarkResult(BaseModel):
    """Result of benchmark execution"""
    task_id: str
    run_id: str
    actual_output: str
    actual_quality: float
    actual_cost: float
    actual_latency_ms: float
    passed: bool
    failure_reason: Optional[str] = None
    executed_at: datetime = Field(default_factory=datetime.now)


class BenchmarkReport(BaseModel):
    """Comprehensive benchmark report"""
    benchmark_id: str
    total_tasks: int
    passed_tasks: int
    failed_tasks: int
    pass_rate: float
    avg_quality: float
    avg_cost: float
    avg_latency_ms: float
    results: List[BenchmarkResult]
    comparison_to_previous: Optional[Dict[str, float]] = None
    created_at: datetime = Field(default_factory=datetime.now)


class BenchmarkRunner:
    """
    Runs offline benchmarks for systematic evaluation
    Compares results across runs for regression detection
    """
    
    def __init__(
        self,
        benchmark_path: str = "benchmarks",
        results_path: str = "artifacts/eval/benchmarks"
    ):
        self.benchmark_path = Path(benchmark_path)
        self.results_path = Path(results_path)
        self.benchmark_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # Load benchmark tasks
        self.tasks = self._load_benchmark_tasks()
    
    def _load_benchmark_tasks(self) -> List[BenchmarkTask]:
        """Load benchmark tasks from config"""
        tasks_file = self.benchmark_path / "tasks.json"
        
        if tasks_file.exists():
            with open(tasks_file) as f:
                data = json.load(f)
                return [BenchmarkTask(**task) for task in data]
        
        # Create default benchmark tasks
        default_tasks = [
            BenchmarkTask(
                task_id="bench_retrieve_001",
                query="What is the capital of France?",
                expected_output="Paris",
                expected_quality_min=0.9,
                max_cost=0.1,
                task_type="retrieve"
            ),
            BenchmarkTask(
                task_id="bench_analyze_001",
                query="Compare Python and JavaScript",
                expected_output=None,
                expected_quality_min=0.8,
                max_cost=0.5,
                task_type="analyze"
            ),
            BenchmarkTask(
                task_id="bench_summarize_001",
                query="Summarize the key points of machine learning",
                expected_output=None,
                expected_quality_min=0.75,
                max_cost=0.3,
                task_type="summarize"
            )
        ]
        
        # Save default tasks
        with open(tasks_file, 'w') as f:
            json.dump([t.model_dump() for t in default_tasks], f, indent=2)
        
        return default_tasks
    
    def run_benchmark(
        self,
        execution_engine: Any,  # The system's execution engine
        benchmark_id: Optional[str] = None
    ) -> BenchmarkReport:
        """
        Run full benchmark suite
        Args:
            execution_engine: Engine to execute tasks
            benchmark_id: Optional identifier for this benchmark run
        Returns:
            BenchmarkReport with all results
        """
        if benchmark_id is None:
            benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        results = []
        
        for task in self.tasks:
            print(f"Running benchmark task: {task.task_id}")
            result = self._execute_task(task, execution_engine)
            results.append(result)
        
        # Compute statistics
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        
        report = BenchmarkReport(
            benchmark_id=benchmark_id,
            total_tasks=len(results),
            passed_tasks=len(passed),
            failed_tasks=len(failed),
            pass_rate=len(passed) / len(results) if results else 0,
            avg_quality=sum(r.actual_quality for r in results) / len(results) if results else 0,
            avg_cost=sum(r.actual_cost for r in results) / len(results) if results else 0,
            avg_latency_ms=sum(r.actual_latency_ms for r in results) / len(results) if results else 0,
            results=results
        )
        
        # Compare to previous benchmark
        previous_report = self._load_latest_report()
        if previous_report:
            report.comparison_to_previous = {
                "quality_delta": report.avg_quality - previous_report.avg_quality,
                "cost_delta": report.avg_cost - previous_report.avg_cost,
                "pass_rate_delta": report.pass_rate - previous_report.pass_rate
            }
        
        # Save report
        self._save_report(report)
        
        return report
    
    def _execute_task(self, task: BenchmarkTask, engine: Any) -> BenchmarkResult:
        """Execute a single benchmark task"""
        try:
            # Simulate execution (in production, would call real engine)
            # For now, create mock result
            result = BenchmarkResult(
                task_id=task.task_id,
                run_id=f"bench_run_{task.task_id}",
                actual_output=f"Simulated output for {task.query}",
                actual_quality=0.85,  # Simulated
                actual_cost=0.05,  # Simulated
                actual_latency_ms=500,  # Simulated
                passed=True
            )
            
            # Check if task passed
            if result.actual_quality < task.expected_quality_min:
                result.passed = False
                result.failure_reason = f"Quality {result.actual_quality} below minimum {task.expected_quality_min}"
            
            if result.actual_cost > task.max_cost:
                result.passed = False
                result.failure_reason = f"Cost {result.actual_cost} exceeds maximum {task.max_cost}"
            
            return result
            
        except Exception as e:
            return BenchmarkResult(
                task_id=task.task_id,
                run_id=f"bench_run_{task.task_id}_failed",
                actual_output="",
                actual_quality=0.0,
                actual_cost=0.0,
                actual_latency_ms=0,
                passed=False,
                failure_reason=f"Execution error: {str(e)}"
            )
    
    def _save_report(self, report: BenchmarkReport):
        """Save benchmark report"""
        path = self.results_path / f"{report.benchmark_id}.json"
        with open(path, 'w') as f:
            f.write(report.model_dump_json(indent=2))
        
        # Also save as "latest"
        latest_path = self.results_path / "latest.json"
        with open(latest_path, 'w') as f:
            f.write(report.model_dump_json(indent=2))
    
    def _load_latest_report(self) -> Optional[BenchmarkReport]:
        """Load most recent benchmark report"""
        latest_path = self.results_path / "latest.json"
        
        if latest_path.exists():
            with open(latest_path) as f:
                data = json.load(f)
                return BenchmarkReport(**data)
        
        return None
    
    def compare_benchmarks(
        self,
        benchmark_id_1: str,
        benchmark_id_2: str
    ) -> Dict[str, Any]:
        """Compare two benchmark runs"""
        path1 = self.results_path / f"{benchmark_id_1}.json"
        path2 = self.results_path / f"{benchmark_id_2}.json"
        
        if not (path1.exists() and path2.exists()):
            return {"error": "One or both benchmarks not found"}
        
        with open(path1) as f:
            report1 = BenchmarkReport(**json.load(f))
        
        with open(path2) as f:
            report2 = BenchmarkReport(**json.load(f))
        
        return {
            "benchmark_1": benchmark_id_1,
            "benchmark_2": benchmark_id_2,
            "quality_change": report2.avg_quality - report1.avg_quality,
            "cost_change": report2.avg_cost - report1.avg_cost,
            "pass_rate_change": report2.pass_rate - report1.pass_rate,
            "regression_detected": report2.pass_rate < report1.pass_rate
        }


# Singleton instance
_runner = None

def get_benchmark_runner() -> BenchmarkRunner:
    """Get singleton BenchmarkRunner instance"""
    global _runner
    if _runner is None:
        _runner = BenchmarkRunner()
    return _runner



