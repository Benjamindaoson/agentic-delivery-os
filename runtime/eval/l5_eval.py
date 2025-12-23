from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime

class EvalResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    run_id: str
    task_type: str
    quality_score: float
    cost: float
    latency: float
    success: bool
    violations: List[str] = []
    timestamp: Any = Field(default_factory=datetime.now)

class BenchmarkTask(BaseModel):
    model_config = ConfigDict(extra='allow')
    task_id: str
    query: str
    difficulty: str
    expected_output_fragment: str
    ground_truth_context: Optional[str] = None

class BenchmarkSuite:
    def __init__(self, benchmark_path: str = "benchmarks", eval_path: str = "artifacts/eval"):
        self.benchmark_path = benchmark_path
        self.eval_path = eval_path
        os.makedirs(benchmark_path, exist_ok=True)
        os.makedirs(eval_path, exist_ok=True)
        self._init_default_tasks()

    def _init_default_tasks(self):
        tasks = [
            BenchmarkTask(task_id="T1", query="What is Agentic OS?", difficulty="easy", expected_output_fragment="multi-agent"),
            BenchmarkTask(task_id="T2", query="How to implement L5 memory?", difficulty="medium", expected_output_fragment="SQLite"),
            BenchmarkTask(task_id="T3", query="Complex RAG with cross-run learning", difficulty="hard", expected_output_fragment="policy versioning")
        ]
        path = f"{self.benchmark_path}/default_tasks.json"
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump([t.model_dump() for t in tasks], f, indent=2)

    def record_eval(self, result: EvalResult):
        path = f"{self.eval_path}/{result.run_id}.json"
        with open(path, "w") as f:
            f.write(result.model_dump_json(indent=2))

    def check_regression(self, current_score: float, task_type: str) -> bool:
        evals = []
        if os.path.exists(self.eval_path):
            for file in os.listdir(self.eval_path):
                if file.endswith(".json"):
                    with open(f"{self.eval_path}/{file}", "r") as f:
                        try:
                            data = json.load(f)
                            if data.get("task_type") == task_type:
                                evals.append(data["quality_score"])
                        except:
                            continue
        
        if not evals:
            return False
        
        avg_score = sum(evals) / len(evals)
        return current_score < (avg_score * 0.95)
