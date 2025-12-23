"""
Retrieval Layer: Vector Store + Evidence Collection
Real FAISS-based retrieval with policy versioning and attribution
"""

from runtime.retrieval.vector_store import (
    VectorStore,
    Document,
    RetrievalResult,
    EvidencePackage,
    EvidenceCollector,
    get_vector_store,
)

from runtime.retrieval.l5_retrieval import (
    RetrievalDecision,
    RetrievalPolicy,
    RetrievalManager,
)

__all__ = [
    # Vector Store
    "VectorStore",
    "Document",
    "RetrievalResult",
    "EvidencePackage",
    "EvidenceCollector",
    "get_vector_store",
    # Policy
    "RetrievalDecision",
    "RetrievalPolicy",
    "RetrievalManager",
]
