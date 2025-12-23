"""
Evidence Contribution Signal: 证据贡献信号
增强 Evidence 层的可观测性，为 Learning 提供归因信号
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class EvidencePack:
    """
    证据包（增强版）：包含证据 ID 和使用状态。
    """
    evidence_id: str  # 唯一证据 ID
    source_doc_id: str  # 来源文档 ID
    chunk_id: str  # 分块 ID
    content_hash: str  # 内容哈希
    relevance_score: float  # 相关性分数
    used_in_final_output: bool = False  # 是否被用于最终输出
    conflict_with: List[str] = field(default_factory=list)  # 冲突的证据 ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def create_evidence_id(source_doc_id: str, chunk_id: str, content: str) -> str:
        """生成唯一证据 ID"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{source_doc_id}:{chunk_id}:{content_hash}"


@dataclass
class EvidenceUsageSummary:
    """
    证据使用摘要：供 TraceStore.run_metrics 记录。
    """
    run_id: str
    total_evidence: int  # 总证据数
    used_evidence: int  # 被使用的证据数
    conflicting_evidence: int  # 冲突证据数
    usage_rate: float = 0.0  # 使用率
    conflict_rate: float = 0.0  # 冲突率
    avg_relevance_used: float = 0.0  # 被使用证据的平均相关性
    avg_relevance_unused: float = 0.0  # 未使用证据的平均相关性
    evidence_ids_used: List[str] = field(default_factory=list)
    evidence_ids_conflicting: List[str] = field(default_factory=list)
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceContributionTracker:
    """
    证据贡献追踪器：追踪证据在生成过程中的贡献。
    
    工作流程：
    1. 检索阶段：收集所有候选证据
    2. 验证阶段：标记冲突证据
    3. 生成阶段：标记被使用的证据
    4. 输出阶段：生成使用摘要
    """
    
    def __init__(self, run_id: str):
        """
        初始化追踪器。
        
        Args:
            run_id: 运行 ID
        """
        self.run_id = run_id
        self._evidence: Dict[str, EvidencePack] = {}
        self._conflicts: List[tuple] = []  # (evidence_id_1, evidence_id_2)
    
    def add_evidence(
        self,
        source_doc_id: str,
        chunk_id: str,
        content: str,
        relevance_score: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvidencePack:
        """
        添加证据。
        
        Args:
            source_doc_id: 来源文档 ID
            chunk_id: 分块 ID
            content: 内容
            relevance_score: 相关性分数
            metadata: 元数据
            
        Returns:
            EvidencePack
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        evidence_id = EvidencePack.create_evidence_id(source_doc_id, chunk_id, content)
        
        pack = EvidencePack(
            evidence_id=evidence_id,
            source_doc_id=source_doc_id,
            chunk_id=chunk_id,
            content_hash=content_hash,
            relevance_score=relevance_score,
            used_in_final_output=False,
            metadata=metadata or {}
        )
        
        self._evidence[evidence_id] = pack
        return pack
    
    def mark_used(self, evidence_id: str) -> None:
        """标记证据被使用"""
        if evidence_id in self._evidence:
            self._evidence[evidence_id].used_in_final_output = True
    
    def mark_conflict(self, evidence_id_1: str, evidence_id_2: str) -> None:
        """标记两个证据冲突"""
        self._conflicts.append((evidence_id_1, evidence_id_2))
        
        if evidence_id_1 in self._evidence:
            self._evidence[evidence_id_1].conflict_with.append(evidence_id_2)
        if evidence_id_2 in self._evidence:
            self._evidence[evidence_id_2].conflict_with.append(evidence_id_1)
    
    def get_evidence(self, evidence_id: str) -> Optional[EvidencePack]:
        """获取证据"""
        return self._evidence.get(evidence_id)
    
    def get_all_evidence(self) -> List[EvidencePack]:
        """获取所有证据"""
        return list(self._evidence.values())
    
    def generate_usage_summary(self) -> EvidenceUsageSummary:
        """
        生成使用摘要。
        
        Returns:
            EvidenceUsageSummary
        """
        all_evidence = list(self._evidence.values())
        total = len(all_evidence)
        
        if total == 0:
            return EvidenceUsageSummary(
                run_id=self.run_id,
                total_evidence=0,
                used_evidence=0,
                conflicting_evidence=0,
                timestamp=datetime.now().isoformat()
            )
        
        used = [e for e in all_evidence if e.used_in_final_output]
        unused = [e for e in all_evidence if not e.used_in_final_output]
        conflicting = set()
        for e in all_evidence:
            if e.conflict_with:
                conflicting.add(e.evidence_id)
        
        used_count = len(used)
        conflicting_count = len(conflicting)
        
        # 计算平均相关性
        avg_relevance_used = sum(e.relevance_score for e in used) / used_count if used_count > 0 else 0.0
        avg_relevance_unused = sum(e.relevance_score for e in unused) / len(unused) if unused else 0.0
        
        return EvidenceUsageSummary(
            run_id=self.run_id,
            total_evidence=total,
            used_evidence=used_count,
            conflicting_evidence=conflicting_count,
            usage_rate=used_count / total,
            conflict_rate=conflicting_count / total,
            avg_relevance_used=round(avg_relevance_used, 4),
            avg_relevance_unused=round(avg_relevance_unused, 4),
            evidence_ids_used=[e.evidence_id for e in used],
            evidence_ids_conflicting=list(conflicting),
            timestamp=datetime.now().isoformat()
        )


class EvidenceStatsCollector:
    """
    证据统计收集器：汇总所有 runs 的证据使用统计。
    """
    
    def __init__(
        self,
        stats_path: str = "artifacts/evidence_stats.json"
    ):
        """
        初始化收集器。
        
        Args:
            stats_path: 统计文件路径
        """
        self.stats_path = stats_path
        self._summaries: List[EvidenceUsageSummary] = []
        self._load()
    
    def record(self, summary: EvidenceUsageSummary) -> None:
        """记录摘要"""
        self._summaries.append(summary)
        
        # 限制历史大小
        if len(self._summaries) > 10000:
            self._summaries = self._summaries[-10000:]
        
        self._save()
    
    def get_aggregate_stats(self, window_size: int = 100) -> Dict[str, Any]:
        """
        获取聚合统计（供 Learning 消费）。
        
        Args:
            window_size: 窗口大小
            
        Returns:
            dict: 聚合统计
        """
        recent = self._summaries[-window_size:] if len(self._summaries) > window_size else self._summaries
        
        if not recent:
            return {
                "window_size": 0,
                "avg_usage_rate": 0.0,
                "avg_conflict_rate": 0.0,
                "avg_total_evidence": 0.0,
                "generated_at": datetime.now().isoformat()
            }
        
        n = len(recent)
        return {
            "window_size": n,
            "avg_usage_rate": sum(s.usage_rate for s in recent) / n,
            "avg_conflict_rate": sum(s.conflict_rate for s in recent) / n,
            "avg_total_evidence": sum(s.total_evidence for s in recent) / n,
            "avg_relevance_used": sum(s.avg_relevance_used for s in recent) / n,
            "avg_relevance_unused": sum(s.avg_relevance_unused for s in recent) / n,
            "generated_at": datetime.now().isoformat()
        }
    
    def _load(self) -> None:
        """加载统计"""
        if not os.path.exists(self.stats_path):
            return
        
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for summary_data in data.get("summaries", []):
                self._summaries.append(EvidenceUsageSummary(
                    run_id=summary_data.get("run_id", ""),
                    total_evidence=summary_data.get("total_evidence", 0),
                    used_evidence=summary_data.get("used_evidence", 0),
                    conflicting_evidence=summary_data.get("conflicting_evidence", 0),
                    usage_rate=summary_data.get("usage_rate", 0.0),
                    conflict_rate=summary_data.get("conflict_rate", 0.0),
                    avg_relevance_used=summary_data.get("avg_relevance_used", 0.0),
                    avg_relevance_unused=summary_data.get("avg_relevance_unused", 0.0),
                    evidence_ids_used=summary_data.get("evidence_ids_used", []),
                    evidence_ids_conflicting=summary_data.get("evidence_ids_conflicting", []),
                    timestamp=summary_data.get("timestamp", "")
                ))
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save(self) -> None:
        """保存统计"""
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        
        data = {
            "summaries": [s.to_dict() for s in self._summaries[-1000:]],  # 只保存最近 1000 条
            "aggregate": self.get_aggregate_stats(),
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例
_evidence_stats_collector: Optional[EvidenceStatsCollector] = None


def get_evidence_stats_collector() -> EvidenceStatsCollector:
    """获取全局证据统计收集器"""
    global _evidence_stats_collector
    if _evidence_stats_collector is None:
        _evidence_stats_collector = EvidenceStatsCollector()
    return _evidence_stats_collector



