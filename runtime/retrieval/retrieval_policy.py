"""
Retrieval Policy: 检索策略版本化 + 归因
将检索逻辑抽象为策略对象，供 Learning 评估和优化
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class ChunkingStrategy(str, Enum):
    """分块策略"""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    DOCUMENT = "document"


class EmbeddingModel(str, Enum):
    """嵌入模型"""
    OPENAI_ADA = "openai_ada"
    OPENAI_3_SMALL = "openai_3_small"
    OPENAI_3_LARGE = "openai_3_large"
    BGE_SMALL = "bge_small"
    BGE_LARGE = "bge_large"
    E5_SMALL = "e5_small"
    E5_LARGE = "e5_large"
    LOCAL = "local"


class RerankStrategy(str, Enum):
    """重排序策略"""
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    COHERE = "cohere"
    LLM_RERANK = "llm_rerank"
    BM25_HYBRID = "bm25_hybrid"


@dataclass
class RetrievalPolicy:
    """
    检索策略定义。
    
    所有检索调用必须使用一个策略对象，供 TraceStore 记录和 Learning 评估。
    """
    policy_id: str
    policy_version: str = "1.0"
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE
    chunking_params: Dict[str, Any] = field(default_factory=dict)
    embedding_model: EmbeddingModel = EmbeddingModel.OPENAI_ADA
    rerank_strategy: RerankStrategy = RerankStrategy.NONE
    top_k: int = 10
    min_similarity: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["chunking_strategy"] = self.chunking_strategy.value
        result["embedding_model"] = self.embedding_model.value
        result["rerank_strategy"] = self.rerank_strategy.value
        return result
    
    def to_hash(self) -> str:
        """生成策略哈希（用于去重和比较）"""
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class RetrievalResult:
    """
    检索结果（带归因信息）。
    """
    policy_id: str
    num_docs: int
    evidence_used_count: int  # 最终被使用的证据数量
    downstream_success: Optional[bool] = None  # 下游任务是否成功
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    query_hash: str = ""
    doc_ids: List[str] = field(default_factory=list)
    similarity_scores: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalPolicyStats:
    """检索策略统计"""
    policy_id: str
    total_invocations: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_docs_used: float = 0.0
    contribution_score: float = 0.0  # 对最终成功的贡献度
    avg_latency_ms: float = 0.0
    total_cost: float = 0.0
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RetrievalPolicyRegistry:
    """
    检索策略注册表。
    
    管理所有可用的检索策略，提供版本化和归因追踪。
    """
    
    def __init__(
        self,
        stats_path: str = "artifacts/retrieval_policy_stats.json"
    ):
        """
        初始化策略注册表。
        
        Args:
            stats_path: 统计文件路径
        """
        self.stats_path = stats_path
        self._policies: Dict[str, RetrievalPolicy] = {}
        self._stats: Dict[str, RetrievalPolicyStats] = {}
        self._results_buffer: List[RetrievalResult] = []
        
        # 注册默认策略
        self._register_default_policies()
        
        # 加载统计
        self._load_stats()
    
    def _register_default_policies(self) -> None:
        """注册默认策略"""
        # 策略 1: 基础策略（固定分块 + OpenAI Ada）
        self.register(RetrievalPolicy(
            policy_id="basic_v1",
            policy_version="1.0",
            chunking_strategy=ChunkingStrategy.FIXED_SIZE,
            chunking_params={"chunk_size": 512, "overlap": 50},
            embedding_model=EmbeddingModel.OPENAI_ADA,
            rerank_strategy=RerankStrategy.NONE,
            top_k=10,
            min_similarity=0.5
        ))
        
        # 策略 2: 语义分块 + 重排序
        self.register(RetrievalPolicy(
            policy_id="semantic_rerank_v1",
            policy_version="1.0",
            chunking_strategy=ChunkingStrategy.SEMANTIC,
            chunking_params={"max_chunk_size": 1024},
            embedding_model=EmbeddingModel.OPENAI_3_SMALL,
            rerank_strategy=RerankStrategy.CROSS_ENCODER,
            top_k=20,
            min_similarity=0.6
        ))
        
        # 策略 3: 混合检索
        self.register(RetrievalPolicy(
            policy_id="hybrid_v1",
            policy_version="1.0",
            chunking_strategy=ChunkingStrategy.PARAGRAPH,
            chunking_params={},
            embedding_model=EmbeddingModel.BGE_LARGE,
            rerank_strategy=RerankStrategy.BM25_HYBRID,
            top_k=15,
            min_similarity=0.55
        ))
    
    def register(self, policy: RetrievalPolicy) -> None:
        """注册策略"""
        self._policies[policy.policy_id] = policy
        
        if policy.policy_id not in self._stats:
            self._stats[policy.policy_id] = RetrievalPolicyStats(
                policy_id=policy.policy_id
            )
    
    def get(self, policy_id: str) -> Optional[RetrievalPolicy]:
        """获取策略"""
        return self._policies.get(policy_id)
    
    def get_default_policy(self) -> RetrievalPolicy:
        """获取默认策略"""
        return self._policies.get("basic_v1") or list(self._policies.values())[0]
    
    def list_policies(self) -> List[RetrievalPolicy]:
        """列出所有策略"""
        return list(self._policies.values())
    
    def record_result(
        self,
        result: RetrievalResult,
        downstream_success: Optional[bool] = None
    ) -> None:
        """
        记录检索结果。
        
        Args:
            result: 检索结果
            downstream_success: 下游任务是否成功
        """
        policy_id = result.policy_id
        result.downstream_success = downstream_success
        
        if policy_id not in self._stats:
            self._stats[policy_id] = RetrievalPolicyStats(policy_id=policy_id)
        
        stats = self._stats[policy_id]
        stats.total_invocations += 1
        
        if downstream_success is True:
            stats.success_count += 1
        elif downstream_success is False:
            stats.failure_count += 1
        
        # 更新成功率
        if stats.total_invocations > 0:
            stats.success_rate = stats.success_count / stats.total_invocations
        
        # 更新平均使用文档数
        n = stats.total_invocations
        stats.avg_docs_used = ((n - 1) * stats.avg_docs_used + result.evidence_used_count) / n
        
        # 更新延迟和成本
        stats.avg_latency_ms = ((n - 1) * stats.avg_latency_ms + result.latency_ms) / n
        stats.total_cost += result.cost_estimate
        
        # 计算贡献度（成功时使用的证据比例）
        if downstream_success and result.num_docs > 0:
            contribution = result.evidence_used_count / result.num_docs
            stats.contribution_score = (
                (stats.success_count - 1) * stats.contribution_score + contribution
            ) / stats.success_count if stats.success_count > 0 else contribution
        
        stats.last_updated = datetime.now().isoformat()
        
        # 持久化
        self._save_stats()
    
    def get_stats(self, policy_id: str) -> Optional[RetrievalPolicyStats]:
        """获取策略统计"""
        return self._stats.get(policy_id)
    
    def get_all_stats(self) -> Dict[str, RetrievalPolicyStats]:
        """获取所有统计"""
        return self._stats.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取检索策略摘要（供 Learning 消费）。
        """
        policies = {}
        for policy_id, stats in self._stats.items():
            policies[policy_id] = {
                "success_rate": stats.success_rate,
                "avg_docs_used": stats.avg_docs_used,
                "contribution_score": stats.contribution_score,
                "total_invocations": stats.total_invocations,
                "avg_latency_ms": stats.avg_latency_ms
            }
        
        return {
            "policies": policies,
            "generated_at": datetime.now().isoformat()
        }
    
    def _load_stats(self) -> None:
        """加载统计"""
        if not os.path.exists(self.stats_path):
            return
        
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for policy_id, stats_data in data.get("policies", {}).items():
                self._stats[policy_id] = RetrievalPolicyStats(
                    policy_id=policy_id,
                    total_invocations=stats_data.get("total_invocations", 0),
                    success_count=stats_data.get("success_count", 0),
                    failure_count=stats_data.get("failure_count", 0),
                    success_rate=stats_data.get("success_rate", 0.0),
                    avg_docs_used=stats_data.get("avg_docs_used", 0.0),
                    contribution_score=stats_data.get("contribution_score", 0.0),
                    avg_latency_ms=stats_data.get("avg_latency_ms", 0.0),
                    total_cost=stats_data.get("total_cost", 0.0),
                    last_updated=stats_data.get("last_updated", "")
                )
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save_stats(self) -> None:
        """保存统计"""
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        
        data = {
            "policies": {
                policy_id: stats.to_dict()
                for policy_id, stats in self._stats.items()
            },
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例
_retrieval_policy_registry: Optional[RetrievalPolicyRegistry] = None


def get_retrieval_policy_registry() -> RetrievalPolicyRegistry:
    """获取全局检索策略注册表"""
    global _retrieval_policy_registry
    if _retrieval_policy_registry is None:
        _retrieval_policy_registry = RetrievalPolicyRegistry()
    return _retrieval_policy_registry



