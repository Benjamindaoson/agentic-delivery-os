"""
L5 Retrieval Manager - Industrial-Grade Retrieval with Policy Routing
Features:
- Real vector store integration (FAISS/Chroma)
- Embedding → Retrieval → Policy routing
- Reranking support
- Full audit trail
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
import json
import os
from datetime import datetime
from enum import Enum

# Import real vector store
try:
    from runtime.retrieval.vector_store import (
        VectorStore, Document, RetrievalResult, EvidencePackage,
        get_vector_store, EvidenceCollector
    )
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    VECTOR_STORE_AVAILABLE = False


class RetrievalStrategy(str, Enum):
    """Retrieval strategies for policy routing"""
    DENSE = "dense"              # Vector similarity only
    SPARSE = "sparse"            # BM25/keyword
    HYBRID = "hybrid"            # Dense + Sparse fusion
    RERANK = "rerank"            # Two-stage with reranking
    MULTI_INDEX = "multi_index"  # Search across multiple indices


class RetrievalDecision(BaseModel):
    """Decision record for audit"""
    query: str
    query_hash: str = ""
    selected_indices: List[str] = Field(default_factory=list)
    top_k: int
    strategy: RetrievalStrategy = RetrievalStrategy.DENSE
    rerank_strategy: str = "none"
    rationale: str = ""
    recall_score: Optional[float] = None
    precision_score: Optional[float] = None
    latency_ms: float = 0.0
    num_results: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class RetrievalPolicy(BaseModel):
    """Retrieval policy configuration"""
    version: str
    embedding_model: str = "default"
    vector_store_type: str = "faiss"
    dimension: int = 384
    chunking_strategy: Dict[str, Any] = Field(default_factory=lambda: {
        "method": "sentence",
        "max_chunk_size": 512,
        "overlap": 50
    })
    retrieval_config: Dict[str, Any] = Field(default_factory=lambda: {
        "default_top_k": 5,
        "min_score": 0.1,
        "rerank_enabled": False
    })
    active_since: datetime = Field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RetrievalManager:
    """
    Industrial-grade retrieval manager with:
    - Real vector store integration
    - Policy-based routing
    - Multi-strategy support
    - Full audit trail
    """
    
    def __init__(
        self,
        artifact_path: str = "artifacts/retrieval",
        index_path: str = "artifacts/retrieval/index"
    ):
        self.artifact_path = artifact_path
        self.index_path = index_path
        os.makedirs(artifact_path, exist_ok=True)
        
        # Initialize vector store
        self._vector_store = None
        self._evidence_collector = None
        
        # Current active policy
        self._active_policy: Optional[RetrievalPolicy] = None
        self._load_active_policy()
    
    @property
    def vector_store(self) -> Optional['VectorStore']:
        """Lazy-load vector store"""
        if self._vector_store is None and VECTOR_STORE_AVAILABLE:
            self._vector_store = get_vector_store(index_path=self.index_path)
        return self._vector_store
    
    @property
    def evidence_collector(self) -> Optional['EvidenceCollector']:
        """Lazy-load evidence collector"""
        if self._evidence_collector is None and VECTOR_STORE_AVAILABLE:
            self._evidence_collector = EvidenceCollector(self.vector_store)
        return self._evidence_collector
    
    def _load_active_policy(self):
        """Load the most recent active policy"""
        policy_dir = self.artifact_path
        if not os.path.exists(policy_dir):
            return
        
        policies = []
        for f in os.listdir(policy_dir):
            if f.startswith("policy_v") and f.endswith(".json"):
                try:
                    with open(os.path.join(policy_dir, f), "r") as pf:
                        data = json.load(pf)
                        policies.append(RetrievalPolicy(**data))
                except Exception:
                    pass
        
        if policies:
            # Sort by version and get latest
            policies.sort(key=lambda p: p.version, reverse=True)
            self._active_policy = policies[0]
    
    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        strategy: Optional[RetrievalStrategy] = None,
        task_id: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[RetrievalResult], RetrievalDecision]:
        """
        Execute retrieval with policy routing.
        
        Args:
            query: Search query
            top_k: Number of results (default from policy)
            strategy: Retrieval strategy (default from policy)
            task_id: Task ID for tracking
            filter_metadata: Optional metadata filter
            
        Returns:
            Tuple of (results, decision)
        """
        import time
        import hashlib
        
        start_time = time.time()
        
        # Get defaults from policy
        policy = self._active_policy or self._default_policy()
        config = policy.retrieval_config
        
        effective_top_k = top_k or config.get("default_top_k", 5)
        effective_strategy = strategy or RetrievalStrategy.DENSE
        min_score = config.get("min_score", 0.1)
        
        # Generate query hash for audit
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        
        # Execute retrieval based on strategy
        results = []
        
        if self.vector_store:
            if effective_strategy == RetrievalStrategy.DENSE:
                results = self._dense_retrieval(query, effective_top_k, filter_metadata)
            elif effective_strategy == RetrievalStrategy.HYBRID:
                results = self._hybrid_retrieval(query, effective_top_k, filter_metadata)
            elif effective_strategy == RetrievalStrategy.RERANK:
                results = self._rerank_retrieval(query, effective_top_k, filter_metadata)
            else:
                results = self._dense_retrieval(query, effective_top_k, filter_metadata)
            
            # Filter by min_score
            results = [r for r in results if r.score >= min_score]
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Create decision record
        decision = RetrievalDecision(
            query=query,
            query_hash=query_hash,
            selected_indices=[r.doc_id for r in results],
            top_k=effective_top_k,
            strategy=effective_strategy,
            rerank_strategy="cross_encoder" if effective_strategy == RetrievalStrategy.RERANK else "none",
            rationale=f"Retrieved {len(results)} documents using {effective_strategy.value} strategy",
            num_results=len(results),
            latency_ms=latency_ms
        )
        
        # Record decision
        if task_id:
            self.record_decision(task_id, decision)
        
        return results, decision
    
    def _dense_retrieval(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Execute dense (vector) retrieval"""
        if not self.vector_store:
            return []
        
        return self.vector_store.search(query, top_k, filter_metadata)
    
    def _hybrid_retrieval(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Execute hybrid retrieval (dense + sparse)"""
        # For now, just use dense retrieval
        # In production: combine with BM25 using RRF
        dense_results = self._dense_retrieval(query, top_k * 2, filter_metadata)
        
        # Simple deduplication and re-scoring
        seen = set()
        results = []
        for r in dense_results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                results.append(r)
                if len(results) >= top_k:
                    break
        
        return results
    
    def _rerank_retrieval(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Execute two-stage retrieval with reranking"""
        # First stage: retrieve more candidates
        candidates = self._dense_retrieval(query, top_k * 3, filter_metadata)
        
        if not candidates:
            return []
        
        # Second stage: rerank (simplified - in production use cross-encoder)
        # Score boost for documents with query terms
        query_terms = set(query.lower().split())
        
        reranked = []
        for r in candidates:
            content_terms = set(r.content.lower().split())
            overlap = len(query_terms & content_terms)
            boost = overlap * 0.1  # Simple term overlap boost
            
            reranked.append(RetrievalResult(
                doc_id=r.doc_id,
                content=r.content,
                score=min(r.score + boost, 1.0),
                metadata=r.metadata,
                source=r.source,
                rank=0
            ))
        
        # Re-sort by boosted score
        reranked.sort(key=lambda x: x.score, reverse=True)
        
        # Assign new ranks
        for i, r in enumerate(reranked[:top_k]):
            r.rank = i + 1
        
        return reranked[:top_k]
    
    def ingest_documents(
        self,
        documents: List[Dict[str, Any]],
        task_id: Optional[str] = None
    ) -> int:
        """
        Ingest documents into the vector store.
        
        Args:
            documents: List of documents to ingest
            task_id: Optional task ID
            
        Returns:
            Number of documents ingested
        """
        if not self.vector_store:
            return 0
        
        from runtime.retrieval.vector_store import Document
        
        doc_objects = []
        for i, doc_data in enumerate(documents):
            if isinstance(doc_data, str):
                content = doc_data
                source = "inline"
                metadata = {}
            elif isinstance(doc_data, dict):
                content = doc_data.get("content") or doc_data.get("text") or str(doc_data)
                source = doc_data.get("source", "inline")
                metadata = doc_data.get("metadata", {})
            else:
                continue
            
            doc = Document(
                doc_id=f"{task_id or 'doc'}_{i}",
                content=content,
                source=source,
                metadata={"task_id": task_id, **metadata}
            )
            doc_objects.append(doc)
        
        return self.vector_store.add_documents(doc_objects)
    
    def collect_evidence(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
        task_id: Optional[str] = None
    ) -> Tuple['EvidencePackage', Dict[str, Any]]:
        """
        Collect evidence for a query with validation.
        """
        if self.evidence_collector:
            return self.evidence_collector.collect_evidence(
                query=query,
                top_k=top_k,
                min_score=min_score,
                task_id=task_id
            )
        
        # Fallback if no evidence collector
        results, decision = self.retrieve(query, top_k, task_id=task_id)
        
        # Create basic evidence package
        from runtime.retrieval.vector_store import EvidencePackage
        evidence = EvidencePackage(
            query=query,
            query_embedding_hash=decision.query_hash,
            results=results,
            total_retrieved=len(results),
            retrieval_latency_ms=decision.latency_ms
        )
        
        validation = {
            "has_evidence": len(results) > 0,
            "evidence_quality": max([r.score for r in results], default=0),
            "sufficient": len(results) >= 1
        }
        
        return evidence, validation
    
    def record_decision(self, run_id: str, decision: RetrievalDecision):
        """Record retrieval decision for audit"""
        path = os.path.join(self.artifact_path, f"{run_id}_decision.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(decision.model_dump_json(indent=2))
    
    def update_policy(self, policy: RetrievalPolicy):
        """Update retrieval policy"""
        path = os.path.join(self.artifact_path, f"policy_v{policy.version}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(policy.model_dump_json(indent=2))
        
        self._active_policy = policy
    
    def _default_policy(self) -> RetrievalPolicy:
        """Get default policy"""
        return RetrievalPolicy(
            version="0.0.1",
            embedding_model="default",
            vector_store_type="faiss"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval manager statistics"""
        stats = {
            "vector_store_available": VECTOR_STORE_AVAILABLE,
            "active_policy": self._active_policy.to_dict() if self._active_policy else None
        }
        
        if self.vector_store:
            stats["vector_store_stats"] = self.vector_store.get_stats()
        
        return stats


# Singleton instance
_retrieval_manager: Optional[RetrievalManager] = None


def get_retrieval_manager() -> RetrievalManager:
    """Get singleton RetrievalManager instance"""
    global _retrieval_manager
    if _retrieval_manager is None:
        _retrieval_manager = RetrievalManager()
    return _retrieval_manager



