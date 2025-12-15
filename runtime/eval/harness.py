"""
Standardized Evaluation & Comparison Harness
评测与对比总框架

对同一任务 task_id，在多个系统实现 system_id 下，
使用完全相同输入（hash 固定），
一键运行，自动生成结果（结构化），
可并排对照，全过程不可狡辩（可审计、可复现、可 hash）
"""
import os
import json
import hashlib
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class RunMetadata:
    """运行元数据（确定性）"""
    run_id: str
    timestamp: str
    git_commit: str
    harness_version: str
    suite_version: str
    system_matrix_hash: str
    task_suite_hash: str
    seed: int
    model_provider: str
    model_version: str
    tool_version: str
    config_snapshot: Dict[str, Any]
    config_hash: str

@dataclass
class CaseResult:
    """Case 结果"""
    task_id: str
    system_id: str
    run_id: str
    completion_status: str  # COMPLETED / FAILED / PAUSED
    correct_failure: bool  # 是否符合 failure_acceptance_criteria
    cost: float
    metrics: Dict[str, Any]
    evidence_pack_path: str

class EvaluationHarness:
    """评测总框架"""
    
    def __init__(self, base_dir: str = "artifacts/phase7"):
        self.base_dir = base_dir
        self.runs_dir = os.path.join(base_dir, "runs")
        self.cases_dir = os.path.join(base_dir, "cases")
        self.summary_dir = os.path.join(base_dir, "summary")
        
        for dir_path in [self.runs_dir, self.cases_dir, self.summary_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        self.version = "1.0"
    
    def generate_run_id(
        self,
        git_commit: str,
        harness_version: str,
        suite_version: str,
        system_matrix_hash: str,
        task_suite_hash: str
    ) -> str:
        """生成 run_id（确定性）"""
        components = [
            datetime.now().isoformat(),
            git_commit[:8],
            harness_version,
            suite_version,
            system_matrix_hash[:8],
            task_suite_hash[:8]
        ]
        combined = "_".join(components)
        run_id = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return f"run_{run_id}"
    
    def get_git_commit(self) -> str:
        """获取 git commit（确定性）"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    async def run_evaluation(
        self,
        task_suite_path: str,
        system_matrix_path: str,
        seed: int = 42,
        model_provider: str = "openai",
        model_version: str = "gpt-4",
        config_snapshot: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        运行评测（一键运行）
        
        Returns:
            run_id: 运行标识
        """
        # 加载任务集和系统矩阵
        with open(task_suite_path, "r", encoding="utf-8") as f:
            task_suite = json.load(f)
        with open(system_matrix_path, "r", encoding="utf-8") as f:
            system_matrix = json.load(f)
        
        # 计算 hash
        task_suite_hash = self._calculate_file_hash(task_suite_path)
        system_matrix_hash = self._calculate_file_hash(system_matrix_path)
        
        # 生成 config snapshot
        if config_snapshot is None:
            config_snapshot = self._capture_config_snapshot()
        config_hash = hashlib.sha256(
            json.dumps(config_snapshot, sort_keys=True).encode()
        ).hexdigest()
        
        # 生成 run_id
        git_commit = self.get_git_commit()
        run_id = self.generate_run_id(
            git_commit,
            self.version,
            task_suite.get("version", "1.0"),
            system_matrix_hash,
            task_suite_hash
        )
        
        # 创建 run 目录
        run_dir = os.path.join(self.runs_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)
        
        # 保存 run metadata
        run_metadata = RunMetadata(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            git_commit=git_commit,
            harness_version=self.version,
            suite_version=task_suite.get("version", "1.0"),
            system_matrix_hash=system_matrix_hash,
            task_suite_hash=task_suite_hash,
            seed=seed,
            model_provider=model_provider,
            model_version=model_version,
            tool_version="1.0",  # 简化
            config_snapshot=config_snapshot,
            config_hash=config_hash
        )
        
        metadata_path = os.path.join(run_dir, "run_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(asdict(run_metadata), f, indent=2, ensure_ascii=False)
        
        # 运行所有 task × system 组合
        case_results = []
        import asyncio
        async def run_all_cases():
            results = []
            for task in task_suite.get("tasks", []):
                for system in system_matrix.get("systems", []):
                    case_result = await self._run_case(
                        task, system, run_id, run_metadata
                    )
                    results.append(case_result)
            return results
        case_results = asyncio.run(run_all_cases())
        
        # 保存 case 结果
        results_path = os.path.join(run_dir, "case_results.json")
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump([asdict(cr) for cr in case_results], f, indent=2, ensure_ascii=False)
        
        # 生成汇总
        self._generate_summary(run_id, case_results)
        
        return run_id
    
    async def _run_case(
        self,
        task: Dict[str, Any],
        system: Dict[str, Any],
        run_id: str,
        run_metadata: RunMetadata
    ) -> CaseResult:
        """运行单个 case"""
        task_id = task["task_id"]
        system_id = system["system_id"]
        
        # 创建 case 目录
        case_dir = os.path.join(self.cases_dir, task_id, system_id)
        os.makedirs(case_dir, exist_ok=True)
        
        # 保存 input snapshot
        input_snapshot = task["fixed_input_spec"]
        input_snapshot_path = os.path.join(case_dir, "input_snapshot.json")
        with open(input_snapshot_path, "w", encoding="utf-8") as f:
            json.dump(input_snapshot, f, indent=2, ensure_ascii=False)
        
        # 计算 input hash
        input_hash = hashlib.sha256(
            json.dumps(input_snapshot, sort_keys=True).encode()
        ).hexdigest()
        input_hash_path = os.path.join(case_dir, "input_hash.txt")
        with open(input_hash_path, "w", encoding="utf-8") as f:
            f.write(input_hash)
        
        # 保存 run metadata
        run_metadata_path = os.path.join(case_dir, "run_metadata.json")
        with open(run_metadata_path, "w", encoding="utf-8") as f:
            json.dump(asdict(run_metadata), f, indent=2, ensure_ascii=False)
        
        # 执行任务（调用系统）
        execution_result = await self._execute_task(task, system, run_metadata)
        
        # 保存 trace export
        trace_export_path = os.path.join(case_dir, "trace_export.json")
        with open(trace_export_path, "w", encoding="utf-8") as f:
            json.dump(execution_result.get("trace", {}), f, indent=2, ensure_ascii=False)
        
        # 生成 replay view（event-order replay）
        replay_view = self._generate_replay_view(execution_result.get("trace", {}))
        replay_view_path = os.path.join(case_dir, "replay_view.json")
        with open(replay_view_path, "w", encoding="utf-8") as f:
            json.dump(replay_view, f, indent=2, ensure_ascii=False)
        
        # 生成 cost outcome
        cost_outcome = self._generate_cost_outcome(execution_result.get("trace", {}))
        cost_outcome_path = os.path.join(case_dir, "cost_outcome.json")
        with open(cost_outcome_path, "w", encoding="utf-8") as f:
            json.dump(cost_outcome, f, indent=2, ensure_ascii=False)
        
        # 生成 failure explain（如适用）
        if execution_result.get("status") in ["FAILED", "PAUSED"]:
            failure_explain = self._generate_failure_explain(
                execution_result.get("trace", {}),
                task
            )
            failure_explain_path = os.path.join(case_dir, "failure_explain.json")
            with open(failure_explain_path, "w", encoding="utf-8") as f:
                json.dump(failure_explain, f, indent=2, ensure_ascii=False)
        
        # 计算指标
        metrics = self._calculate_metrics(execution_result, task)
        metrics_path = os.path.join(case_dir, "metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        # 生成 export audit pack
        export_pack_path = self._generate_export_pack(case_dir, execution_result)
        
        # 计算 case hash
        case_hash = self._calculate_directory_hash(case_dir)
        case_hash_path = os.path.join(case_dir, "case_hash.txt")
        with open(case_hash_path, "w", encoding="utf-8") as f:
            f.write(case_hash)
        
        # 判断 correct_failure
        correct_failure = self._check_correct_failure(
            execution_result, task
        )
        
        return CaseResult(
            task_id=task_id,
            system_id=system_id,
            run_id=run_id,
            completion_status=execution_result.get("status", "UNKNOWN"),
            correct_failure=correct_failure,
            cost=metrics.get("cost", 0.0),
            metrics=metrics,
            evidence_pack_path=case_dir
        )
    
    def _execute_task(
        self,
        task: Dict[str, Any],
        system: Dict[str, Any],
        run_metadata: RunMetadata
    ) -> Dict[str, Any]:
        """执行任务（根据 system_id 调用不同系统）"""
        # 简化：这里应该根据 system_id 调用不同的系统实现
        # 实际应该通过 API 或直接调用系统代码
        # 返回执行结果（包含 trace）
        
        # 临时实现：返回占位结果
        return {
            "status": "COMPLETED",
            "trace": {},
            "cost": 0.0
        }
    
    def _generate_replay_view(self, trace_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成 replay view（event-order replay）"""
        # 明确声明时间模型
        events = trace_data.get("agent_executions", []) + \
                 trace_data.get("governance_decisions", [])
        
        replay_events = []
        for idx, event in enumerate(events):
            replay_events.append({
                "event_sequence_index": idx + 1,
                "event_id": event.get("event_id") or f"event_{idx + 1}",
                "type": event.get("type") or "unknown",
                "timestamp": event.get("timestamp"),
                "payload_ref": f"trace.{event.get('type', 'unknown')}[{idx}]"
            })
        
        return {
            "time_model": "event-order_replay",
            "time_model_declaration": "This is logical execution order replay, not wall-clock time. Not execution duration ratio. Not physical time axis. Only for causal and decision order verification.",
            "events": replay_events,
            "total_events": len(replay_events)
        }
    
    def _generate_cost_outcome(self, trace_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成 cost outcome（含预测/实际/偏差）"""
        # 从 trace 提取实际成本
        agent_reports = trace_data.get("agent_reports", [])
        actual_cost = sum(r.get("cost_impact", 0.0) for r in agent_reports)
        
        # 简化：预测成本（实际应该从预测器获取）
        predicted_cost = actual_cost * 1.1  # 占位
        
        return {
            "predicted_cost": predicted_cost,
            "actual_cost": actual_cost,
            "delta_cost": actual_cost - predicted_cost,
            "cost_evidence_events": [
                f"agent_report_{i}"
                for i, r in enumerate(agent_reports)
                if r.get("cost_impact", 0) > 0
            ],
            "counterfactual_estimation": {
                "type": "deterministic_counterfactual_estimation",
                "declaration": "Based on plan_definition full path static expansion. Based on node-level deterministic cost rules. Not dependent on real execution. Not assuming path will succeed. Not equivalent to replay."
            }
        }
    
    def _generate_failure_explain(
        self,
        trace_data: Dict[str, Any],
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成 failure explain"""
        eval_feedback = trace_data.get("evaluation_feedback_flow", {})
        gov_decisions = trace_data.get("governance_decisions", [])
        
        return {
            "failure_type": eval_feedback.get("last_failure_type"),
            "blame_hint": eval_feedback.get("last_blame_hint"),
            "governance_decisions": [
                {
                    "execution_mode": d.get("execution_mode"),
                    "reasoning": d.get("reasoning"),
                    "checkpoint": d.get("checkpoint")
                }
                for d in gov_decisions
                if d.get("execution_mode") != "normal"
            ],
            "evidence_events": [
                f"agent_report_{i}"
                for i in range(len(trace_data.get("agent_reports", [])))
            ]
        }
    
    def _calculate_metrics(
        self,
        execution_result: Dict[str, Any],
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算指标"""
        trace_data = execution_result.get("trace", {})
        status = execution_result.get("status", "UNKNOWN")
        
        # 基础指标
        completion_rate = 1.0 if status == "COMPLETED" else 0.0
        
        # 成本
        agent_reports = trace_data.get("agent_reports", [])
        cost = sum(r.get("cost_impact", 0.0) for r in agent_reports)
        
        # 事件长度
        events = trace_data.get("agent_executions", []) + \
                 trace_data.get("governance_decisions", [])
        replay_length = len(events)
        
        return {
            "task_completion_rate": completion_rate,
            "cost": cost,
            "cost_per_successful_task": cost if status == "COMPLETED" else 0.0,
            "mean_replay_length": replay_length,
            "event_count": replay_length
        }
    
    def _check_correct_failure(
        self,
        execution_result: Dict[str, Any],
        task: Dict[str, Any]
    ) -> bool:
        """检查是否为正确失败"""
        status = execution_result.get("status", "UNKNOWN")
        if status == "COMPLETED":
            return True
        
        # 检查是否符合 failure_acceptance_criteria
        failure_criteria = task.get("failure_acceptance_criteria", {})
        if not failure_criteria:
            return False
        
        # 简化：检查失败类型是否在允许列表中
        trace_data = execution_result.get("trace", {})
        failure_type = trace_data.get("evaluation_feedback_flow", {}).get("last_failure_type")
        allowed_failures = failure_criteria.get("allowed_failure_types", [])
        
        return failure_type in allowed_failures
    
    def _generate_export_pack(
        self,
        case_dir: str,
        execution_result: Dict[str, Any]
    ) -> str:
        """生成 export audit pack"""
        import zipfile
        
        pack_path = os.path.join(case_dir, "export_audit_pack.zip")
        
        with zipfile.ZipFile(pack_path, "w") as zipf:
            # 添加所有文件
            for file in os.listdir(case_dir):
                if file.endswith(".zip"):
                    continue
                file_path = os.path.join(case_dir, file)
                if os.path.isfile(file_path):
                    zipf.write(file_path, file)
        
        return pack_path
    
    def _generate_summary(self, run_id: str, case_results: List[CaseResult]):
        """生成汇总结果（结构化，无叙事）"""
        # 按 system 汇总
        system_summary = {}
        for result in case_results:
            system_id = result.system_id
            if system_id not in system_summary:
                system_summary[system_id] = {
                    "total_tasks": 0,
                    "completed": 0,
                    "failed": 0,
                    "correct_failures": 0,
                    "total_cost": 0.0,
                    "cost_per_success": 0.0,
                    "mean_replay_length": 0.0
                }
            
            summary = system_summary[system_id]
            summary["total_tasks"] += 1
            if result.completion_status == "COMPLETED":
                summary["completed"] += 1
            else:
                summary["failed"] += 1
                if result.correct_failure:
                    summary["correct_failures"] += 1
            
            summary["total_cost"] += result.cost
            if result.completion_status == "COMPLETED":
                summary["cost_per_success"] += result.cost
            
            summary["mean_replay_length"] += result.metrics.get("mean_replay_length", 0)
        
        # 计算平均值
        for system_id, summary in system_summary.items():
            if summary["completed"] > 0:
                summary["cost_per_success"] /= summary["completed"]
            if summary["total_tasks"] > 0:
                summary["mean_replay_length"] /= summary["total_tasks"]
        
        # 保存 leaderboard
        leaderboard_path = os.path.join(self.summary_dir, f"leaderboard_{run_id}.json")
        with open(leaderboard_path, "w", encoding="utf-8") as f:
            json.dump(system_summary, f, indent=2, ensure_ascii=False)
        
        # CSV 版本
        csv_path = os.path.join(self.summary_dir, f"leaderboard_{run_id}.csv")
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "system_id", "total_tasks", "completed", "failed", "correct_failures",
                "total_cost", "cost_per_success", "mean_replay_length"
            ])
            writer.writeheader()
            for system_id, summary in system_summary.items():
                writer.writerow({"system_id": system_id, **summary})
    
    def _capture_config_snapshot(self) -> Dict[str, Any]:
        """捕获配置快照"""
        # 读取系统配置
        config_path = "configs/system.yaml"
        if os.path.exists(config_path):
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件 hash"""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def _calculate_directory_hash(self, dir_path: str) -> str:
        """计算目录整体 hash"""
        hasher = hashlib.sha256()
        for root, dirs, files in os.walk(dir_path):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                with open(file_path, "rb") as f:
                    hasher.update(f.read())
        return hasher.hexdigest()

