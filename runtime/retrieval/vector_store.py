"""
Vector Store: Real FAISS-based vector storage and retrieval
Provides document embedding, indexing, and similarity search capabilities.
"""
import os
import json
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
from dataclasses import dataclass, asdict

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None


class Document(BaseModel):
    """A document chunk for retrieval"""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    chunk_index: int = 0
    embedding: Optional[List[float]] = None


class RetrievalResult(BaseModel):
    """Result of a retrieval operation"""
    doc_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    rank: int = 0


class EvidencePackage(BaseModel):
    """Evidence package for a query"""
    query: str
    query_embedding_hash: str
    results: List[RetrievalResult]
    total_retrieved: int
    retrieval_latency_ms: float
    rerank_applied: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class VectorStore:
    """
    FAISS-based vector store for document retrieval.
    
    Features:
    - Real FAISS index for similarity search
    - Document persistence to disk
    - Embedding caching
    - Evidence package generation for audit
    """
    
    def __init__(
        self,
        dimension: int = 384,
        index_path: str = "artifacts/retrieval/index",
        use_gpu: bool = False
    ):
        self.dimension = dimension
        self.index_path = index_path
        self.use_gpu = use_gpu
        
        # Create directories
        os.makedirs(index_path, exist_ok=True)
        
        # Document storage
        self.documents: Dict[str, Document] = {}
        self.id_to_idx: Dict[str, int] = {}
        self.idx_to_id: Dict[int, str] = {}
        
        # Initialize FAISS index
        self.index = self._create_index()
        
        # Load existing data if available
        self._load_state()
    
    def _create_index(self) -> Optional[Any]:
        """Create FAISS index"""
        if not FAISS_AVAILABLE:
            return None
        
        # Use L2 distance (Euclidean) for similarity
        index = faiss.IndexFlatL2(self.dimension)
        
        # Optionally wrap with ID map for document tracking
        index = faiss.IndexIDMap(index)
        
        return index
    
    def _load_state(self):
        """Load persisted state from disk"""
        docs_path = os.path.join(self.index_path, "documents.json")
        index_file = os.path.join(self.index_path, "faiss.index")
        
        # Load documents
        if os.path.exists(docs_path):
            try:
                with open(docs_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for doc_data in data.get("documents", []):
                        doc = Document(**doc_data)
                        self.documents[doc.doc_id] = doc
                    self.id_to_idx = data.get("id_to_idx", {})
                    self.idx_to_id = {int(k): v for k, v in data.get("idx_to_id", {}).items()}
            except Exception:
                pass
        
        # Load FAISS index
        if FAISS_AVAILABLE and os.path.exists(index_file):
            try:
                self.index = faiss.read_index(index_file)
            except Exception:
                self.index = self._create_index()
    
    def _save_state(self):
        """Persist state to disk"""
        docs_path = os.path.join(self.index_path, "documents.json")
        index_file = os.path.join(self.index_path, "faiss.index")
        
        # Save documents
        data = {
            "documents": [doc.model_dump() for doc in self.documents.values()],
            "id_to_idx": self.id_to_idx,
            "idx_to_id": {str(k): v for k, v in self.idx_to_id.items()}
        }
        with open(docs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        # Save FAISS index
        if FAISS_AVAILABLE and self.index is not None:
            try:
                faiss.write_index(self.index, index_file)
            except Exception:
                pass
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for text.
        
        In production, this should call a real embedding model (e.g., sentence-transformers).
        For now, uses a deterministic hash-based embedding for consistency.
        """
        # Deterministic embedding based on text hash
        # In production: use sentence-transformers, OpenAI embeddings, etc.
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert hash to float vector
        np.random.seed(int(text_hash[:8], 16) % (2**32))
        embedding = np.random.randn(self.dimension).astype(np.float32)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def add_documents(self, documents: List[Document]) -> int:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents to add
            
        Returns:
            Number of documents added
        """
        if not FAISS_AVAILABLE:
            # Fallback: store documents without indexing
            for doc in documents:
                self.documents[doc.doc_id] = doc
            self._save_state()
            return len(documents)
        
        added = 0
        embeddings = []
        ids = []
        
        for doc in documents:
            # Skip if already exists
            if doc.doc_id in self.documents:
                continue
            
            # Generate embedding if not provided
            if doc.embedding is None:
                embedding = self.embed_text(doc.content)
                doc.embedding = embedding.tolist()
            else:
                embedding = np.array(doc.embedding, dtype=np.float32)
            
            # Assign index
            idx = len(self.documents)
            self.documents[doc.doc_id] = doc
            self.id_to_idx[doc.doc_id] = idx
            self.idx_to_id[idx] = doc.doc_id
            
            embeddings.append(embedding)
            ids.append(idx)
            added += 1
        
        # Add to FAISS index
        if embeddings:
            embeddings_array = np.vstack(embeddings).astype(np.float32)
            ids_array = np.array(ids, dtype=np.int64)
            self.index.add_with_ids(embeddings_array, ids_array)
        
        self._save_state()
        return added
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Search for similar documents.
        
        Args:
            query: Query string
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of retrieval results
        """
        import time
        start_time = time.time()
        
        if not FAISS_AVAILABLE or self.index is None or len(self.documents) == 0:
            # Fallback: simple text matching
            return self._fallback_search(query, top_k, filter_metadata)
        
        # Generate query embedding
        query_embedding = self.embed_text(query).reshape(1, -1)
        
        # Search in FAISS
        # Request more results for filtering
        search_k = min(top_k * 3, len(self.documents))
        distances, indices = self.index.search(query_embedding, search_k)
        
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:
                continue
            
            doc_id = self.idx_to_id.get(int(idx))
            if doc_id is None:
                continue
            
            doc = self.documents.get(doc_id)
            if doc is None:
                continue
            
            # Apply metadata filter
            if filter_metadata:
                match = all(
                    doc.metadata.get(k) == v
                    for k, v in filter_metadata.items()
                )
                if not match:
                    continue
            
            # Convert L2 distance to similarity score (0-1)
            # Lower distance = higher similarity
            score = 1.0 / (1.0 + float(dist))
            
            results.append(RetrievalResult(
                doc_id=doc.doc_id,
                content=doc.content,
                score=score,
                metadata=doc.metadata,
                source=doc.source,
                rank=len(results) + 1
            ))
            
            if len(results) >= top_k:
                break
        
        return results
    
    def _fallback_search(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Fallback search using simple text matching"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_docs = []
        for doc in self.documents.values():
            # Apply metadata filter
            if filter_metadata:
                match = all(
                    doc.metadata.get(k) == v
                    for k, v in filter_metadata.items()
                )
                if not match:
                    continue
            
            # Simple word overlap scoring
            content_lower = doc.content.lower()
            content_words = set(content_lower.split())
            
            overlap = len(query_words & content_words)
            score = overlap / max(len(query_words), 1)
            
            # Boost if query appears as substring
            if query_lower in content_lower:
                score += 0.5
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # Sort by score descending
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for i, (doc, score) in enumerate(scored_docs[:top_k]):
            results.append(RetrievalResult(
                doc_id=doc.doc_id,
                content=doc.content,
                score=min(score, 1.0),
                metadata=doc.metadata,
                source=doc.source,
                rank=i + 1
            ))
        
        return results
    
    def retrieve_with_evidence(
        self,
        query: str,
        top_k: int = 5,
        task_id: Optional[str] = None
    ) -> EvidencePackage:
        """
        Retrieve documents and package as evidence for audit.
        
        Args:
            query: Query string
            top_k: Number of results
            task_id: Optional task ID for artifact storage
            
        Returns:
            Evidence package with retrieval results
        """
        import time
        start_time = time.time()
        
        # Perform search
        results = self.search(query, top_k)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Generate query embedding hash for audit
        query_embedding = self.embed_text(query)
        query_hash = hashlib.sha256(query_embedding.tobytes()).hexdigest()[:16]
        
        # Create evidence package
        evidence = EvidencePackage(
            query=query,
            query_embedding_hash=query_hash,
            results=results,
            total_retrieved=len(results),
            retrieval_latency_ms=latency_ms,
            rerank_applied=False
        )
        
        # Save evidence artifact if task_id provided
        if task_id:
            self._save_evidence_artifact(task_id, evidence)
        
        return evidence
    
    def _save_evidence_artifact(self, task_id: str, evidence: EvidencePackage):
        """Save evidence package to artifacts"""
        artifact_dir = os.path.join("artifacts", "retrieval", task_id)
        os.makedirs(artifact_dir, exist_ok=True)
        
        evidence_path = os.path.join(artifact_dir, "evidence.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(evidence.model_dump_json(indent=2))
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID"""
        return self.documents.get(doc_id)
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document (note: FAISS doesn't support direct deletion)"""
        if doc_id in self.documents:
            del self.documents[doc_id]
            self._save_state()
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            "total_documents": len(self.documents),
            "dimension": self.dimension,
            "faiss_available": FAISS_AVAILABLE,
            "index_path": self.index_path,
            "index_size": self.index.ntotal if FAISS_AVAILABLE and self.index else 0
        }


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store(
    dimension: int = 384,
    index_path: str = "artifacts/retrieval/index"
) -> VectorStore:
    """Get singleton VectorStore instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(dimension=dimension, index_path=index_path)
    return _vector_store


class EvidenceCollector:
    """
    Collects and validates evidence for RAG responses.
    Ensures answers are grounded in retrieved documents.
    """
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
    
    def collect_evidence(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
        task_id: Optional[str] = None
    ) -> Tuple[EvidencePackage, Dict[str, Any]]:
        """
        Collect evidence for a query.
        
        Returns:
            Tuple of (evidence_package, validation_result)
        """
        # Retrieve evidence
        evidence = self.vector_store.retrieve_with_evidence(query, top_k, task_id)
        
        # Validate evidence quality
        validation = self._validate_evidence(evidence, min_score)
        
        return evidence, validation
    
    def _validate_evidence(
        self,
        evidence: EvidencePackage,
        min_score: float
    ) -> Dict[str, Any]:
        """Validate evidence quality"""
        results = evidence.results
        
        # Calculate metrics
        if not results:
            return {
                "has_evidence": False,
                "evidence_quality": 0.0,
                "top_score": 0.0,
                "avg_score": 0.0,
                "sufficient": False,
                "reason": "No documents retrieved"
            }
        
        scores = [r.score for r in results]
        top_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        # Check if evidence is sufficient
        sufficient = top_score >= min_score and len(results) >= 1
        
        return {
            "has_evidence": True,
            "evidence_quality": top_score,
            "top_score": top_score,
            "avg_score": avg_score,
            "num_results": len(results),
            "sufficient": sufficient,
            "reason": "Evidence collected successfully" if sufficient else f"Top score {top_score:.2f} below threshold {min_score}"
        }
    
    def format_context(
        self,
        evidence: EvidencePackage,
        max_tokens: int = 2000
    ) -> str:
        """Format evidence as context for LLM"""
        if not evidence.results:
            return "No relevant documents found."
        
        context_parts = []
        current_tokens = 0
        
        for i, result in enumerate(evidence.results):
            # Estimate tokens (rough: 4 chars per token)
            content_tokens = len(result.content) // 4
            
            if current_tokens + content_tokens > max_tokens:
                break
            
            context_parts.append(
                f"[Document {i+1}] (score: {result.score:.2f})\n"
                f"Source: {result.source or 'unknown'}\n"
                f"{result.content}\n"
            )
            current_tokens += content_tokens
        
        return "\n---\n".join(context_parts)


