"""
Benchmark Suite: Standardized test tasks for system evaluation.
Provides reproducible benchmarks across system versions.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib


class BenchmarkDifficulty(str, Enum):
    """Benchmark difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class BenchmarkCategory(str, Enum):
    """Benchmark categories."""
    RAG_QA = "rag_qa"
    SUMMARIZATION = "summarization"
    REASONING = "reasoning"
    EXTRACTION = "extraction"
    GENERATION = "generation"
    MULTI_HOP = "multi_hop"


@dataclass
class BenchmarkTask:
    """A single benchmark task."""
    task_id: str
    name: str
    description: str
    
    category: BenchmarkCategory
    difficulty: BenchmarkDifficulty
    
    # Input
    input_data: Dict[str, Any]
    
    # Expected output / evaluation criteria
    expected_output: Optional[Dict[str, Any]] = None
    evaluation_criteria: List[Dict[str, Any]] = field(default_factory=list)
    
    # Constraints
    max_cost: float = 0.5
    max_latency_ms: int = 30000
    min_quality: float = 0.7
    
    # Metadata
    version: str = "1.0"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "evaluation_criteria": self.evaluation_criteria,
            "max_cost": self.max_cost,
            "max_latency_ms": self.max_latency_ms,
            "min_quality": self.min_quality,
            "version": self.version,
            "created_at": self.created_at
        }


@dataclass
class BenchmarkResult:
    """Result of running a benchmark task."""
    task_id: str
    run_id: str
    
    # Outcome
    success: bool
    output: Dict[str, Any]
    
    # Metrics
    cost: float
    latency_ms: float
    quality_score: float
    
    # Evaluation details
    criteria_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Pass/fail against constraints
    within_cost: bool = True
    within_latency: bool = True
    above_quality: bool = True
    
    # Metadata
    executed_at: str = ""
    policy_version: str = "unknown"
    
    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def passed(self) -> bool:
        """Check if benchmark passed all constraints."""
        return self.success and self.within_cost and self.within_latency and self.above_quality


@dataclass
class BenchmarkRun:
    """A complete benchmark suite run."""
    run_id: str
    suite_name: str
    
    # Results
    results: List[BenchmarkResult]
    
    # Summary
    total_tasks: int = 0
    passed_tasks: int = 0
    failed_tasks: int = 0
    
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    avg_quality: float = 0.0
    
    # Metadata
    started_at: str = ""
    completed_at: str = ""
    policy_version: str = "unknown"
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "suite_name": self.suite_name,
            "results": [r.to_dict() for r in self.results],
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "failed_tasks": self.failed_tasks,
            "pass_rate": self.passed_tasks / self.total_tasks if self.total_tasks > 0 else 0,
            "total_cost": round(self.total_cost, 4),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "avg_quality": round(self.avg_quality, 4),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "policy_version": self.policy_version
        }


class BenchmarkSuite:
    """
    Manages benchmark tasks and execution.
    
    Provides:
    - Standard task sets by difficulty
    - Reproducible execution
    - Regression detection
    """
    
    def __init__(self, benchmarks_dir: str = "benchmarks"):
        self.benchmarks_dir = benchmarks_dir
        self.tasks_dir = os.path.join(benchmarks_dir, "tasks")
        self.results_dir = os.path.join(benchmarks_dir, "results")
        
        os.makedirs(self.tasks_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        self._tasks: Dict[str, BenchmarkTask] = {}
        self._init_default_tasks()
        self._load_tasks()
    
    def _init_default_tasks(self) -> None:
        """Initialize default benchmark tasks."""
        default_tasks = [
            # Easy RAG QA
            BenchmarkTask(
                task_id="easy_rag_qa_001",
                name="Simple Factual Question",
                description="Answer a simple factual question",
                category=BenchmarkCategory.RAG_QA,
                difficulty=BenchmarkDifficulty.EASY,
                input_data={
                    "query": "What is the capital of France?",
                    "context": "France is a country in Western Europe. Its capital is Paris."
                },
                expected_output={"answer": "Paris"},
                evaluation_criteria=[
                    {"type": "contains", "value": "Paris", "weight": 1.0}
                ],
                max_cost=0.1,
                max_latency_ms=5000
            ),
            BenchmarkTask(
                task_id="easy_rag_qa_002",
                name="Date Extraction",
                description="Extract a date from context",
                category=BenchmarkCategory.RAG_QA,
                difficulty=BenchmarkDifficulty.EASY,
                input_data={
                    "query": "When was the company founded?",
                    "context": "Acme Corp was founded in 1995 by John Smith."
                },
                expected_output={"answer": "1995"},
                evaluation_criteria=[
                    {"type": "contains", "value": "1995", "weight": 1.0}
                ]
            ),
            
            # Medium RAG QA
            BenchmarkTask(
                task_id="medium_rag_qa_001",
                name="Multi-fact Question",
                description="Answer requiring multiple facts",
                category=BenchmarkCategory.RAG_QA,
                difficulty=BenchmarkDifficulty.MEDIUM,
                input_data={
                    "query": "Compare the populations of Tokyo and New York",
                    "context": "Tokyo has approximately 14 million people. New York City has about 8.3 million residents."
                },
                evaluation_criteria=[
                    {"type": "contains", "value": "14 million", "weight": 0.4},
                    {"type": "contains", "value": "8.3 million", "weight": 0.4},
                    {"type": "mentions_comparison", "weight": 0.2}
                ],
                min_quality=0.75
            ),
            
            # Hard Multi-hop
            BenchmarkTask(
                task_id="hard_multihop_001",
                name="Multi-hop Reasoning",
                description="Requires connecting information across sources",
                category=BenchmarkCategory.MULTI_HOP,
                difficulty=BenchmarkDifficulty.HARD,
                input_data={
                    "query": "Who is the CEO of the company that acquired Twitter?",
                    "context": [
                        "Twitter was acquired by X Corp in 2023.",
                        "X Corp is led by Elon Musk as CEO."
                    ]
                },
                expected_output={"answer": "Elon Musk"},
                evaluation_criteria=[
                    {"type": "contains", "value": "Elon Musk", "weight": 0.8},
                    {"type": "reasoning_chain", "weight": 0.2}
                ],
                max_cost=0.3,
                max_latency_ms=20000
            ),
            
            # Summarization
            BenchmarkTask(
                task_id="medium_summary_001",
                name="Document Summarization",
                description="Summarize a document",
                category=BenchmarkCategory.SUMMARIZATION,
                difficulty=BenchmarkDifficulty.MEDIUM,
                input_data={
                    "query": "Summarize the key points",
                    "context": "Machine learning is a subset of artificial intelligence. It enables computers to learn from data without being explicitly programmed. Common applications include image recognition, natural language processing, and recommendation systems."
                },
                evaluation_criteria=[
                    {"type": "contains", "value": "machine learning", "weight": 0.3},
                    {"type": "contains", "value": "artificial intelligence", "weight": 0.3},
                    {"type": "max_length", "value": 100, "weight": 0.2},
                    {"type": "coherence", "weight": 0.2}
                ]
            ),
            
            # Expert reasoning
            BenchmarkTask(
                task_id="expert_reasoning_001",
                name="Complex Analysis",
                description="Requires expert-level reasoning",
                category=BenchmarkCategory.REASONING,
                difficulty=BenchmarkDifficulty.EXPERT,
                input_data={
                    "query": "Analyze the trade-offs between microservices and monolithic architecture for a startup with limited resources",
                    "context": "The startup has 5 developers and needs to launch in 3 months."
                },
                evaluation_criteria=[
                    {"type": "mentions", "value": "scalability", "weight": 0.2},
                    {"type": "mentions", "value": "complexity", "weight": 0.2},
                    {"type": "mentions", "value": "time to market", "weight": 0.2},
                    {"type": "recommendation_present", "weight": 0.2},
                    {"type": "reasoning_quality", "weight": 0.2}
                ],
                max_cost=0.5,
                max_latency_ms=45000,
                min_quality=0.8
            )
        ]
        
        for task in default_tasks:
            self._tasks[task.task_id] = task
            self._save_task(task)
    
    def get_task(self, task_id: str) -> Optional[BenchmarkTask]:
        """Get a benchmark task."""
        return self._tasks.get(task_id)
    
    def get_tasks_by_difficulty(
        self,
        difficulty: BenchmarkDifficulty
    ) -> List[BenchmarkTask]:
        """Get tasks by difficulty level."""
        return [
            t for t in self._tasks.values()
            if t.difficulty == difficulty
        ]
    
    def get_tasks_by_category(
        self,
        category: BenchmarkCategory
    ) -> List[BenchmarkTask]:
        """Get tasks by category."""
        return [
            t for t in self._tasks.values()
            if t.category == category
        ]
    
    def list_all_tasks(self) -> List[BenchmarkTask]:
        """List all tasks."""
        return list(self._tasks.values())
    
    def evaluate_result(
        self,
        task: BenchmarkTask,
        output: Dict[str, Any],
        cost: float,
        latency_ms: float
    ) -> BenchmarkResult:
        """
        Evaluate a task result.
        
        Args:
            task: The benchmark task
            output: The output produced
            cost: Cost incurred
            latency_ms: Latency in ms
            
        Returns:
            BenchmarkResult
        """
        # Evaluate criteria
        criteria_results = []
        total_score = 0.0
        total_weight = 0.0
        
        output_text = str(output.get("output", output.get("answer", "")))
        
        for criterion in task.evaluation_criteria:
            ctype = criterion.get("type", "")
            cvalue = criterion.get("value", "")
            weight = criterion.get("weight", 1.0)
            
            passed = False
            score = 0.0
            
            if ctype == "contains":
                passed = str(cvalue).lower() in output_text.lower()
                score = 1.0 if passed else 0.0
            elif ctype == "mentions":
                passed = str(cvalue).lower() in output_text.lower()
                score = 1.0 if passed else 0.0
            elif ctype == "max_length":
                passed = len(output_text) <= int(cvalue)
                score = 1.0 if passed else 0.0
            elif ctype in ["coherence", "reasoning_quality", "reasoning_chain", 
                          "recommendation_present", "mentions_comparison"]:
                # Simplified scoring for demo
                score = 0.8
                passed = True
            else:
                score = 0.5
            
            criteria_results.append({
                "criterion": ctype,
                "value": cvalue,
                "weight": weight,
                "passed": passed,
                "score": score
            })
            
            total_score += score * weight
            total_weight += weight
        
        quality_score = total_score / total_weight if total_weight > 0 else 0.0
        
        result = BenchmarkResult(
            task_id=task.task_id,
            run_id=f"bench_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            success=quality_score >= task.min_quality,
            output=output,
            cost=cost,
            latency_ms=latency_ms,
            quality_score=quality_score,
            criteria_results=criteria_results,
            within_cost=cost <= task.max_cost,
            within_latency=latency_ms <= task.max_latency_ms,
            above_quality=quality_score >= task.min_quality
        )
        
        return result
    
    def run_suite(
        self,
        suite_name: str,
        tasks: Optional[List[str]] = None,
        difficulty: Optional[BenchmarkDifficulty] = None,
        executor_fn=None
    ) -> BenchmarkRun:
        """
        Run a benchmark suite.
        
        Args:
            suite_name: Name for this run
            tasks: Optional list of task IDs to run
            difficulty: Optional difficulty filter
            executor_fn: Function to execute tasks (takes task, returns output, cost, latency)
            
        Returns:
            BenchmarkRun with all results
        """
        # Select tasks
        if tasks:
            task_list = [self._tasks[tid] for tid in tasks if tid in self._tasks]
        elif difficulty:
            task_list = self.get_tasks_by_difficulty(difficulty)
        else:
            task_list = list(self._tasks.values())
        
        run_id = f"suite_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        results = []
        
        for task in task_list:
            if executor_fn:
                output, cost, latency = executor_fn(task)
            else:
                # Simulated execution for testing
                output = {"output": "Simulated response"}
                cost = 0.05
                latency = 1500.0
            
            result = self.evaluate_result(task, output, cost, latency)
            results.append(result)
        
        # Create run summary
        benchmark_run = BenchmarkRun(
            run_id=run_id,
            suite_name=suite_name,
            results=results,
            total_tasks=len(results),
            passed_tasks=sum(1 for r in results if r.passed),
            failed_tasks=sum(1 for r in results if not r.passed),
            total_cost=sum(r.cost for r in results),
            total_latency_ms=sum(r.latency_ms for r in results),
            avg_quality=sum(r.quality_score for r in results) / len(results) if results else 0
        )
        benchmark_run.completed_at = datetime.now().isoformat()
        
        # Save results
        self._save_run(benchmark_run)
        
        return benchmark_run
    
    def compare_runs(
        self,
        run_id_a: str,
        run_id_b: str
    ) -> Dict[str, Any]:
        """Compare two benchmark runs for regression detection."""
        run_a = self._load_run(run_id_a)
        run_b = self._load_run(run_id_b)
        
        if not run_a or not run_b:
            return {"error": "Run not found"}
        
        comparison = {
            "run_a": run_id_a,
            "run_b": run_id_b,
            "pass_rate_delta": (run_b["passed_tasks"] / run_b["total_tasks"]) - 
                               (run_a["passed_tasks"] / run_a["total_tasks"]),
            "cost_delta": run_b["total_cost"] - run_a["total_cost"],
            "quality_delta": run_b["avg_quality"] - run_a["avg_quality"],
            "latency_delta": run_b["total_latency_ms"] - run_a["total_latency_ms"],
            "regression_detected": False
        }
        
        # Detect regression
        if comparison["pass_rate_delta"] < -0.1:
            comparison["regression_detected"] = True
            comparison["regression_reason"] = "Pass rate dropped significantly"
        elif comparison["quality_delta"] < -0.1:
            comparison["regression_detected"] = True
            comparison["regression_reason"] = "Quality score dropped"
        
        return comparison
    
    def _save_task(self, task: BenchmarkTask) -> None:
        """Save task to file."""
        path = os.path.join(self.tasks_dir, f"{task.task_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_tasks(self) -> None:
        """Load all tasks from files."""
        if not os.path.exists(self.tasks_dir):
            return
        
        for filename in os.listdir(self.tasks_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.tasks_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    task = self._dict_to_task(data)
                    self._tasks[task.task_id] = task
                except (json.JSONDecodeError, IOError, KeyError):
                    pass
    
    def _save_run(self, run: BenchmarkRun) -> None:
        """Save run results."""
        path = os.path.join(self.results_dir, f"{run.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(run.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load run results."""
        path = os.path.join(self.results_dir, f"{run_id}.json")
        if not os.path.exists(path):
            return None
        
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _dict_to_task(self, data: Dict[str, Any]) -> BenchmarkTask:
        """Convert dict to BenchmarkTask."""
        return BenchmarkTask(
            task_id=data["task_id"],
            name=data["name"],
            description=data["description"],
            category=BenchmarkCategory(data["category"]),
            difficulty=BenchmarkDifficulty(data["difficulty"]),
            input_data=data["input_data"],
            expected_output=data.get("expected_output"),
            evaluation_criteria=data.get("evaluation_criteria", []),
            max_cost=data.get("max_cost", 0.5),
            max_latency_ms=data.get("max_latency_ms", 30000),
            min_quality=data.get("min_quality", 0.7),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", "")
        )



