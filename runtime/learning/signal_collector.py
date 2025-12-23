"""
Signal Collector: 集成 Layer 5-9 信号收集
在每次 Run 完成后，自动收集并记录完整因果链信号到 TraceStore
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from runtime.tooling.tool_metrics import get_tool_metrics_collector
from runtime.memory.working_memory import get_working_memory
from runtime.retrieval.retrieval_policy import get_retrieval_policy_registry
from runtime.rag_delivery.evidence_contribution import get_evidence_stats_collector
from runtime.llm.prompt_tracking import get_prompt_tracker
from runtime.analysis.decision_attributor import DecisionAttributor
from runtime.metrics.policy_kpi_aggregator import PolicyKPIAggregator
from runtime.exploration.exploration_engine import ExplorationEngine


@dataclass
class RunSignalSummary:
    """
    单次 Run 的信号摘要。
    
    用于 Learning v1 消费，包含 Tool → Retrieval → Evidence → Generation 的完整因果链。
    """
    run_id: str
    timestamp: str
    
    # Layer 5: Tooling
    tool_calls: int = 0
    tool_success_rate: float = 0.0
    tool_failure_types: Dict[str, int] = None
    tool_total_latency_ms: float = 0.0
    
    # Layer 6: Memory
    pattern_hash: str = ""
    pattern_is_new: bool = False
    pattern_historical_success_rate: float = 0.0
    
    # Layer 7: Retrieval
    retrieval_policy_id: str = ""
    retrieval_num_docs: int = 0
    retrieval_policy_historical_success_rate: float = 0.0
    
    # Layer 8: Evidence
    evidence_total: int = 0
    evidence_used: int = 0
    evidence_usage_rate: float = 0.0
    evidence_conflict_count: int = 0
    
    # Layer 9: Generation
    generation_template_id: str = ""
    generation_token_count: int = 0
    generation_latency_ms: float = 0.0
    generation_cost: float = 0.0
    
    # 最终结果
    run_success: bool = False
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    
    def __post_init__(self):
        if self.tool_failure_types is None:
            self.tool_failure_types = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SignalCollector:
    """
    信号收集器：整合 Layer 5-9 各层的信号。
    
    在每次 Run 完成后调用 collect_and_record()，将信号写入 TraceStore。
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        """
        初始化信号收集器。
        
        Args:
            artifacts_dir: artifacts 目录路径
        """
        self.artifacts_dir = artifacts_dir
        self.signals_path = os.path.join(artifacts_dir, "run_signals.json")
        
        # 获取各层收集器（使用全局实例）
        self.tool_metrics = get_tool_metrics_collector()
        self.working_memory = get_working_memory()
        self.retrieval_registry = get_retrieval_policy_registry()
        self.evidence_stats = get_evidence_stats_collector()
        self.prompt_tracker = get_prompt_tracker()
        
        # 历史信号
        self._signals: List[RunSignalSummary] = []
        self._load()
    
    def collect_run_signals(
        self,
        run_id: str,
        tool_sequence: List[str],
        planner_choice: str,
        retrieval_policy_id: str,
        evidence_summary: Dict[str, Any],
        generation_info: Dict[str, Any],
        run_success: bool
    ) -> RunSignalSummary:
        """
        收集单次 Run 的信号。
        
        Args:
            run_id: Run ID
            tool_sequence: 工具调用序列
            planner_choice: 计划选择
            retrieval_policy_id: 检索策略 ID
            evidence_summary: 证据使用摘要
            generation_info: 生成信息
            run_success: Run 是否成功
            
        Returns:
            RunSignalSummary
        """
        now = datetime.now().isoformat()
        
        # === Layer 5: Tooling ===
        tool_summary = self.tool_metrics.get_summary()
        tool_stats_total = sum(
            t.get("total_invocations", 0)
            for t in tool_summary.get("tools", {}).values()
        )
        tool_success_total = sum(
            t.get("total_invocations", 0) * t.get("success_rate", 0)
            for t in tool_summary.get("tools", {}).values()
        )
        
        # === Layer 6: Memory ===
        pattern_signature = self.working_memory.build_pattern_signature_from_run(
            tool_sequence=tool_sequence,
            planner_choice=planner_choice,
            retrieval_strategy_id=retrieval_policy_id,
            evidence_count=evidence_summary.get("used_evidence", 0),
            generation_template_id=generation_info.get("template_id", "")
        )
        pattern_hash = pattern_signature.to_hash()
        existing_pattern = self.working_memory.get_pattern(pattern_hash)
        
        # === Layer 7: Retrieval ===
        retrieval_stats = self.retrieval_registry.get_stats(retrieval_policy_id)
        
        # === 构建信号摘要 ===
        summary = RunSignalSummary(
            run_id=run_id,
            timestamp=now,
            
            # Layer 5
            tool_calls=len(tool_sequence),
            tool_success_rate=tool_success_total / tool_stats_total if tool_stats_total > 0 else 1.0,
            tool_failure_types={},  # 需要从具体 run 的 trace 中提取
            tool_total_latency_ms=0.0,
            
            # Layer 6
            pattern_hash=pattern_hash,
            pattern_is_new=existing_pattern is None,
            pattern_historical_success_rate=(
                existing_pattern.success_count / existing_pattern.total_count
                if existing_pattern and existing_pattern.total_count > 0
                else 0.0
            ),
            
            # Layer 7
            retrieval_policy_id=retrieval_policy_id,
            retrieval_num_docs=evidence_summary.get("total_evidence", 0),
            retrieval_policy_historical_success_rate=(
                retrieval_stats.success_rate if retrieval_stats else 0.0
            ),
            
            # Layer 8
            evidence_total=evidence_summary.get("total_evidence", 0),
            evidence_used=evidence_summary.get("used_evidence", 0),
            evidence_usage_rate=evidence_summary.get("usage_rate", 0.0),
            evidence_conflict_count=evidence_summary.get("conflicting_evidence", 0),
            
            # Layer 9
            generation_template_id=generation_info.get("template_id", ""),
            generation_token_count=generation_info.get("token_count", 0),
            generation_latency_ms=generation_info.get("latency_ms", 0.0),
            generation_cost=generation_info.get("cost", 0.0),
            
            # 最终结果
            run_success=run_success,
            total_cost=generation_info.get("cost", 0.0),
            total_latency_ms=generation_info.get("latency_ms", 0.0)
        )
        
        return summary
    
    def record_run_signals(
        self,
        summary: RunSignalSummary,
        also_update_memory: bool = True,
        generate_attribution: bool = False,
        update_policy_kpis: bool = False,
        trigger_exploration: bool = False,
        feedback_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        记录 Run 信号。
        
        Args:
            summary: 信号摘要
            also_update_memory: 是否同时更新 Working Memory
            generate_attribution: 是否生成决策归因（shadow-only）
            update_policy_kpis: 是否刷新策略 KPI（shadow-only）
            trigger_exploration: 是否触发探索引擎（shadow-only，不影响主流程）
        """
        # 添加到历史
        self._signals.append(summary)
        
        # 限制大小
        if len(self._signals) > 10000:
            self._signals = self._signals[-10000:]
        
        # 持久化
        self._save()
        
        # 更新 Working Memory
        if also_update_memory:
            signature = self.working_memory.build_pattern_signature_from_run(
                tool_sequence=[],  # 已在 pattern_hash 中
                planner_choice="normal",  # 简化
                retrieval_strategy_id=summary.retrieval_policy_id,
                evidence_count=summary.evidence_used,
                generation_template_id=summary.generation_template_id
            )
            # 由于我们已经有 pattern_hash，直接使用它
            self.working_memory.record(
                signature,
                outcome="success" if summary.run_success else "failure",
                cost=summary.total_cost,
                latency_ms=summary.total_latency_ms
            )

        # Shadow-only L5 hooks
        if generate_attribution:
            try:
                attributor = DecisionAttributor(artifacts_dir=self.artifacts_dir)
                # Best effort: planner info not available here
                asyncio_run = getattr(__import__("asyncio"), "get_event_loop")().run_until_complete
                asyncio_run(
                    attributor.attribute(
                        run_id=summary.run_id,
                        run_signals=summary.to_dict(),
                        planner_decision=None,
                    )
                )
            except Exception:
                # shadow hook failures must not break execution
                pass

        if update_policy_kpis:
            try:
                aggregator = PolicyKPIAggregator(artifacts_dir=self.artifacts_dir)
                asyncio_run = getattr(__import__("asyncio"), "get_event_loop")().run_until_complete
                asyncio_run(aggregator.aggregate())
            except Exception:
                pass

        if trigger_exploration:
            try:
                exploration = ExplorationEngine(artifacts_dir=self.artifacts_dir)
                asyncio_run = getattr(__import__("asyncio"), "get_event_loop")().run_until_complete
                asyncio_run(
                    exploration.maybe_explore(
                        run_id=summary.run_id,
                        run_signals=summary.to_dict(),
                        attribution=None,
                        policy_kpis=None,
                        feedback_events=feedback_events,
                    )
                )
            except Exception:
                pass
    
    def get_recent_signals(self, n: int = 100) -> List[RunSignalSummary]:
        """获取最近 N 个 Run 的信号"""
        return self._signals[-n:]
    
    def get_learning_dataset(self) -> List[Dict[str, Any]]:
        """
        获取 Learning 可消费的数据集。
        
        返回结构化的信号列表，可直接用于 Learning v1 训练。
        """
        return [s.to_dict() for s in self._signals]
    
    def get_aggregate_stats(self) -> Dict[str, Any]:
        """获取聚合统计"""
        if not self._signals:
            return {
                "total_runs": 0,
                "success_rate": 0.0,
                "generated_at": datetime.now().isoformat()
            }
        
        total = len(self._signals)
        success = sum(1 for s in self._signals if s.run_success)
        
        return {
            "total_runs": total,
            "success_rate": success / total,
            "avg_evidence_usage_rate": sum(s.evidence_usage_rate for s in self._signals) / total,
            "avg_total_cost": sum(s.total_cost for s in self._signals) / total,
            "pattern_reuse_rate": sum(1 for s in self._signals if not s.pattern_is_new) / total,
            "generated_at": datetime.now().isoformat()
        }
    
    def _load(self) -> None:
        """加载历史信号"""
        if not os.path.exists(self.signals_path):
            return
        
        try:
            with open(self.signals_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for signal_data in data.get("signals", []):
                self._signals.append(RunSignalSummary(
                    run_id=signal_data.get("run_id", ""),
                    timestamp=signal_data.get("timestamp", ""),
                    tool_calls=signal_data.get("tool_calls", 0),
                    tool_success_rate=signal_data.get("tool_success_rate", 0.0),
                    tool_failure_types=signal_data.get("tool_failure_types", {}),
                    tool_total_latency_ms=signal_data.get("tool_total_latency_ms", 0.0),
                    pattern_hash=signal_data.get("pattern_hash", ""),
                    pattern_is_new=signal_data.get("pattern_is_new", False),
                    pattern_historical_success_rate=signal_data.get("pattern_historical_success_rate", 0.0),
                    retrieval_policy_id=signal_data.get("retrieval_policy_id", ""),
                    retrieval_num_docs=signal_data.get("retrieval_num_docs", 0),
                    retrieval_policy_historical_success_rate=signal_data.get("retrieval_policy_historical_success_rate", 0.0),
                    evidence_total=signal_data.get("evidence_total", 0),
                    evidence_used=signal_data.get("evidence_used", 0),
                    evidence_usage_rate=signal_data.get("evidence_usage_rate", 0.0),
                    evidence_conflict_count=signal_data.get("evidence_conflict_count", 0),
                    generation_template_id=signal_data.get("generation_template_id", ""),
                    generation_token_count=signal_data.get("generation_token_count", 0),
                    generation_latency_ms=signal_data.get("generation_latency_ms", 0.0),
                    generation_cost=signal_data.get("generation_cost", 0.0),
                    run_success=signal_data.get("run_success", False),
                    total_cost=signal_data.get("total_cost", 0.0),
                    total_latency_ms=signal_data.get("total_latency_ms", 0.0)
                ))
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save(self) -> None:
        """保存信号"""
        os.makedirs(os.path.dirname(self.signals_path), exist_ok=True)
        
        data = {
            "signals": [s.to_dict() for s in self._signals[-1000:]],
            "aggregate": self.get_aggregate_stats(),
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.signals_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例
_signal_collector: Optional[SignalCollector] = None


def get_signal_collector() -> SignalCollector:
    """获取全局信号收集器"""
    global _signal_collector
    if _signal_collector is None:
        _signal_collector = SignalCollector()
    return _signal_collector

