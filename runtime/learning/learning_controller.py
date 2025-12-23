"""
Learning Controller: 自动学习触发控制器
在 Run 完成后自动判断是否触发 Learning v1，完全后台化、对用户无感。
"""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from runtime.platform.trace_store import TraceStore
from runtime.learning.dataset_builder import build_training_examples, export_training_dataset
from runtime.learning.policy_trainer import train_policy_from_examples, save_policy_artifact
from runtime.agent_registry.version_resolver import resolve_active_policy
from learning.semantic_task_success import compute_semantic_reward


class LearningController:
    """
    自动学习控制器：在 Run 完成后自动触发 Learning v1。
    
    触发策略（规则型，非 ML）：
    - 条件 A（主）：total_runs >= min_runs AND failure_rate > max_failure_rate
    - 条件 B（版本节奏）：距上次训练的 run 数 >= min_runs_between_training
    """
    
    def __init__(
        self,
        trace_store: TraceStore,
        policy_dir: str = "artifacts/policies",
        min_runs: int = 500,
        max_failure_rate: float = 0.15,
        min_runs_between_training: int = 1000,
    ):
        """
        初始化 Learning Controller。
        
        Args:
            trace_store: TraceStore 实例
            policy_dir: policy artifact 存储目录
            min_runs: 触发学习的最小 run 数
            max_failure_rate: 触发学习的最大失败率阈值
            min_runs_between_training: 两次训练之间的最小 run 数
        """
        self.trace_store = trace_store
        self.policy_dir = policy_dir
        self.min_runs = min_runs
        self.max_failure_rate = max_failure_rate
        self.min_runs_between_training = min_runs_between_training
    
    def should_train(self) -> bool:
        """
        判断是否需要触发一次 Learning v1。
        
        规则（满足任一条件即触发）：
        - 条件 A（主）：total_runs >= min_runs AND failure_rate > max_failure_rate
        - 条件 B（版本节奏）：距上次训练的 run 数 >= min_runs_between_training
        
        Returns:
            bool: True 表示需要触发学习
        """
        # 统计总 run 数和失败率
        stats = self._get_run_statistics()
        total_runs = stats["total_runs"]
        failure_rate = stats["failure_rate"]
        
        # 条件 A（主）：total_runs >= min_runs AND failure_rate > max_failure_rate
        condition_a = (total_runs >= self.min_runs) and (failure_rate > self.max_failure_rate)
        
        # 条件 B（版本节奏）：距上次训练的 run 数 >= min_runs_between_training
        condition_b = self._should_train_by_interval(total_runs)
        
        return condition_a or condition_b
    
    def run_learning_pipeline(self) -> Dict[str, Any]:
        """
        自动执行 Learning v1 流程：
        1. dataset_builder.build_training_examples
        2. policy_trainer.train_policy_from_examples
        3. save_policy_artifact
        4. 自动切换为 active（版本 rollout）
        
        Returns:
            dict: 训练摘要（JSON）
        """
        pipeline_start = datetime.now()
        
        try:
            # Record recent reward trace for auditability
            self._record_reward_trace(limit=50)
            
            # Step 1: 构建训练样本
            examples = build_training_examples(
                self.trace_store,
                max_examples=10000  # 最多使用最近 10k runs
            )
            
            if not examples:
                return {
                    "success": False,
                    "reason": "no_training_examples",
                    "timestamp": pipeline_start.isoformat()
                }
            
            # Step 2: 导出数据集（可选，用于审计）
            dataset_dir = os.path.join("artifacts", "datasets")
            os.makedirs(dataset_dir, exist_ok=True)
            dataset_path = os.path.join(
                dataset_dir,
                f"training_{pipeline_start.strftime('%Y%m%d_%H%M%S')}.jsonl"
            )
            export_training_dataset(examples, dataset_path)
            
            # Step 3: 训练 policy（基于规则统计，非 ML）
            # 获取当前 active policy 作为 base（平滑更新）
            try:
                base_policy = resolve_active_policy(policy_dir=self.policy_dir)
            except Exception:
                base_policy = None
            
            policy = train_policy_from_examples(examples, base_policy=base_policy)
            
            # Step 4: 保存 policy artifact
            os.makedirs(self.policy_dir, exist_ok=True)
            policy_path = save_policy_artifact(policy, self.policy_dir)
            
            # Step 5: 记录训练元数据（用于下次判断是否需要训练）
            self._record_training_metadata(policy, len(examples))
            
            pipeline_end = datetime.now()
            duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            
            # 训练摘要
            summary = {
                "success": True,
                "policy_version": policy["policy_version"],
                "policy_path": policy_path,
                "training_examples_count": len(examples),
                "dataset_path": dataset_path,
                "plan_selection_rules": policy["plan_selection_rules"],
                "thresholds": policy["thresholds"],
                "statistics": policy["metadata"]["statistics"],
                "pipeline_duration_ms": duration_ms,
                "timestamp": pipeline_start.isoformat()
            }

            # --- L5 readiness: consume auxiliary signals (shadow-only, optional) ---
            summary["decision_attribution_sample"] = self._load_optional_json(
                os.path.join("artifacts", "attributions", "latest.json")
            )
            summary["policy_kpis"] = self._load_optional_json(
                os.path.join("artifacts", "policy_kpis.json")
            )
            summary["regression_verdict"] = self._load_optional_json(
                os.path.join("artifacts", "policy_regression_report.json")
            )
            # feedback events tail for learning context
            feedback = self._load_optional_json(os.path.join("artifacts", "feedback_events.json"))
            if feedback:
                summary["feedback_events_tail"] = feedback.get("events", [])[-20:]
            
            return summary
        
        except Exception as e:
            pipeline_end = datetime.now()
            duration_ms = int((pipeline_end - pipeline_start).total_seconds() * 1000)
            
            return {
                "success": False,
                "reason": "pipeline_error",
                "error": str(e),
                "pipeline_duration_ms": duration_ms,
                "timestamp": pipeline_start.isoformat()
            }

    def _record_reward_trace(self, limit: int = 50):
        """
        Generate reward_trace.json using semantic task success for recent runs.
        """
        summaries_dir = getattr(self.trace_store, "summaries_dir", None)
        if not summaries_dir or not os.path.exists(summaries_dir):
            return

        try:
            files = [f for f in os.listdir(summaries_dir) if f.endswith(".json")]
            files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(summaries_dir, x)), reverse=True)[:limit]
            reward_entries: List[Dict[str, Any]] = []
            for f in files:
                path = os.path.join(summaries_dir, f)
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                task_id = data.get("task_id") or f.replace(".json", "")
                quality = data.get("quality_score", 0.5)
                grounding = data.get("grounded_rate", data.get("grounding_score", 0.5))
                cost = data.get("cost", 0.0)
                budget = max(data.get("budget_limit", 1.0), 0.001)
                cost_eff = max(0.0, 1.0 - cost / budget)
                intent_match = data.get("user_intent_match", 0.5)
                reward, detail = compute_semantic_reward(
                    quality_score=quality,
                    grounding_score=grounding,
                    cost_efficiency=cost_eff,
                    user_intent_match=intent_match,
                    task_id=task_id,
                )
                entry = {"task_id": task_id, "reward": reward, **detail}
                reward_entries.append(entry)

            trace_path = os.path.join("artifacts", "reward_trace.json")
            os.makedirs(os.path.dirname(trace_path), exist_ok=True)
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(reward_entries, f, indent=2, ensure_ascii=False)
        except Exception:
            # best-effort
            pass
    
    def _get_run_statistics(self) -> Dict[str, Any]:
        """
        从 TraceStore 获取 run 统计信息。
        
        Returns:
            dict: {"total_runs": int, "failure_rate": float, "success_count": int, "failed_count": int}
        """
        # 查询所有任务（不过滤）
        all_task_ids = self.trace_store.query_tasks({})
        
        if not all_task_ids:
            # 如果索引为空，尝试从 summaries 目录读取
            summaries_dir = self.trace_store.summaries_dir
            if os.path.exists(summaries_dir):
                all_task_ids = [
                    f[:-5] for f in os.listdir(summaries_dir)
                    if f.endswith('.json')
                ]
        
        total_runs = len(all_task_ids)
        
        if total_runs == 0:
            return {
                "total_runs": 0,
                "failure_rate": 0.0,
                "success_count": 0,
                "failed_count": 0
            }
        
        # 统计成功和失败
        success_count = 0
        failed_count = 0
        
        for task_id in all_task_ids:
            summary = self.trace_store.load_summary(task_id)
            if summary:
                final_state = summary.state
                if final_state in ["COMPLETED", "SUCCESS"]:
                    success_count += 1
                elif final_state in ["FAILED", "ERROR", "CANCELLED"]:
                    failed_count += 1
        
        failure_rate = failed_count / total_runs if total_runs > 0 else 0.0
        
        return {
            "total_runs": total_runs,
            "failure_rate": failure_rate,
            "success_count": success_count,
            "failed_count": failed_count
        }
    
    def _should_train_by_interval(self, current_total_runs: int) -> bool:
        """
        基于版本节奏判断是否需要训练（条件 B）。
        
        检查：距上次训练的 run 数 >= min_runs_between_training
        
        Args:
            current_total_runs: 当前总 run 数
            
        Returns:
            bool: True 表示满足间隔条件
        """
        # 读取上次训练的元数据
        metadata_path = os.path.join(self.policy_dir, "training_metadata.json")
        if not os.path.exists(metadata_path):
            # 如果从未训练过，检查是否达到最小训练 run 数
            return current_total_runs >= self.min_runs_between_training
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            last_training_runs = metadata.get("total_runs_at_training", 0)
            runs_since_last_training = current_total_runs - last_training_runs
            
            return runs_since_last_training >= self.min_runs_between_training
        
        except (json.JSONDecodeError, KeyError):
            # 如果元数据损坏，使用默认策略
            return current_total_runs >= self.min_runs_between_training
    
    def _record_training_metadata(self, policy: Dict[str, Any], examples_count: int) -> None:
        """
        记录训练元数据（用于下次判断）。
        
        Args:
            policy: 训练生成的 policy
            examples_count: 训练样本数量
        """
        stats = self._get_run_statistics()
        
        metadata = {
            "policy_version": policy["policy_version"],
            "trained_at": datetime.now().isoformat(),
            "training_examples_count": examples_count,
            "total_runs_at_training": stats["total_runs"],
            "failure_rate_at_training": stats["failure_rate"],
            "success_count_at_training": stats["success_count"],
            "failed_count_at_training": stats["failed_count"]
        }
        
        metadata_path = os.path.join(self.policy_dir, "training_metadata.json")
        os.makedirs(self.policy_dir, exist_ok=True)
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _load_optional_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Best-effort JSON loader that never raises."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

