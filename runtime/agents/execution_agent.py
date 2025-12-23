"""
Execution Agent: 构建工程
Real implementation with:
- Tool-based execution via ToolDispatcher
- Retrieval integration via VectorStore
- Index building
- Evidence collection
- Artifact generation
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, List, Optional, Tuple
from runtime.tools.tool_dispatcher import ToolDispatcher
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader
import os
import json
from datetime import datetime


class ExecutionAgent(BaseAgent):
    """
    Real Execution Agent implementation.
    
    Responsibilities:
    - Generate RAG system configuration
    - Build vector index from documents
    - Collect evidence for queries
    - Generate deliverable artifacts
    - Coordinate tool execution
    """
    
    def __init__(self):
        super().__init__("Execution")
        self.tool_dispatcher = ToolDispatcher()
        self.tool_executions: List[Dict[str, Any]] = []
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
        
        # Lazy-loaded vector store
        self._vector_store = None
        self._evidence_collector = None
    
    @property
    def vector_store(self):
        """Lazy-load vector store"""
        if self._vector_store is None:
            try:
                from runtime.retrieval.vector_store import get_vector_store
                self._vector_store = get_vector_store()
            except ImportError:
                self._vector_store = None
        return self._vector_store
    
    @property
    def evidence_collector(self):
        """Lazy-load evidence collector"""
        if self._evidence_collector is None:
            try:
                from runtime.retrieval.vector_store import EvidenceCollector
                self._evidence_collector = EvidenceCollector(self.vector_store)
            except ImportError:
                self._evidence_collector = None
        return self._evidence_collector
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Execute RAG system construction.
        
        Workflow:
        1. Generate configuration
        2. Ingest documents (if provided)
        3. Build vector index
        4. Collect evidence (if query provided)
        5. Generate output artifacts
        """
        self.tool_executions = []
        spec = context.get("spec", {})
        
        # Track artifacts
        artifacts = {
            "config_generated": False,
            "index_built": False,
            "documents_ingested": 0,
            "evidence_collected": False,
            "output_generated": False
        }
        
        # Collect execution issues
        issues = []
        
        # Step 1: Generate configuration file
        config_result = await self._generate_config(context, task_id)
        self.tool_executions.append(config_result)
        artifacts["config_generated"] = config_result.get("success", False)
        
        if not artifacts["config_generated"]:
            issues.append(f"Config generation failed: {config_result.get('error')}")
        
        # Step 2: Ingest documents if provided
        data_sources = spec.get("data_sources", [])
        documents = spec.get("documents", [])
        inline_content = spec.get("content") or spec.get("data")
        
        ingested_count = 0
        
        if self.vector_store:
            # Ingest from data sources
            if data_sources:
                count = await self._ingest_data_sources(data_sources, task_id)
                ingested_count += count
            
            # Ingest inline documents
            if documents:
                count = await self._ingest_documents(documents, task_id)
                ingested_count += count
            
            # Ingest inline content
            if inline_content:
                count = await self._ingest_inline_content(inline_content, task_id)
                ingested_count += count
            
            artifacts["documents_ingested"] = ingested_count
            
            if ingested_count > 0:
                artifacts["index_built"] = True
        else:
            issues.append("Vector store not available - skipping document ingestion")
        
        # Step 3: Collect evidence if query provided
        query = context.get("query") or spec.get("query")
        evidence = []
        evidence_package = None
        
        if query and self.evidence_collector:
            evidence_package, validation = self.evidence_collector.collect_evidence(
                query=query,
                top_k=spec.get("top_k", 5),
                min_score=spec.get("min_score", 0.1),
                task_id=task_id
            )
            
            if validation.get("has_evidence"):
                evidence = [r.model_dump() for r in evidence_package.results]
                artifacts["evidence_collected"] = True
            else:
                issues.append(f"Evidence collection: {validation.get('reason')}")
        
        # Step 4: Generate output (if LLM available and evidence exists)
        output = None
        llm_meta = {"llm_used": False}
        
        if query and evidence:
            output, llm_meta = await self._generate_output(
                query=query,
                evidence=evidence,
                context=context,
                task_id=task_id
            )
            
            if output:
                artifacts["output_generated"] = True
        
        # Step 5: Generate delivery manifest
        manifest_result = await self._generate_manifest(
            task_id=task_id,
            spec=spec,
            artifacts=artifacts,
            evidence_count=len(evidence),
            output=output
        )
        self.tool_executions.append(manifest_result)
        
        # Determine decision
        critical_artifacts = ["config_generated"]
        all_critical_ok = all(artifacts.get(a, False) for a in critical_artifacts)
        
        if all_critical_ok:
            decision = "execution_complete"
            reason = f"工程执行完成 (配置已生成, 索引文档: {ingested_count})"
        else:
            decision = "execution_partial"
            reason = f"部分执行完成: {'; '.join(issues[:3])}"
        
        return {
            "decision": decision,
            "reason": reason,
            "artifacts": artifacts,
            "evidence": evidence,
            "output": output,
            "tool_executions": [
                t.to_dict() if hasattr(t, "to_dict") else t
                for t in self.tool_executions
            ],
            "llm_result": llm_meta,
            "issues": issues,
            "state_update": {
                "execution_agent_executed": True,
                "artifacts": artifacts,
                "evidence": evidence,
                "output": output
            }
        }
    
    async def _generate_config(
        self,
        context: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """Generate RAG configuration file"""
        spec = context.get("spec", {})
        
        config_content = f"""# RAG System Configuration
# Generated by Agentic AI Delivery OS
# Task ID: {task_id}
# Generated at: {datetime.now().isoformat()}

project:
  name: {spec.get('project_name', 'rag_project')}
  version: "1.0.0"

data_sources:
{self._format_yaml_list(spec.get('data_sources', []))}

embedding:
  model: {spec.get('embedding_model', 'default')}
  dimension: 384

vector_store:
  type: {spec.get('vector_store', 'faiss')}
  index_path: "artifacts/retrieval/index"

retrieval:
  top_k: {spec.get('top_k', 5)}
  min_score: {spec.get('min_score', 0.1)}
  rerank: {spec.get('rerank', False)}

generation:
  model: {spec.get('generation_model', 'default')}
  max_tokens: {spec.get('max_tokens', 512)}
  temperature: {spec.get('temperature', 0.0)}
"""
        
        # Use tool dispatcher to write file
        result = await self.tool_dispatcher.execute(
            "file_write",
            {
                "path": f"artifacts/rag_project/{task_id}/config.yaml",
                "content": config_content
            },
            task_id
        )
        
        return {
            "tool": "file_write",
            "success": result.success,
            "output": result.output,
            "error": result.error
        }
    
    def _format_yaml_list(self, items: List[Any]) -> str:
        """Format list for YAML"""
        if not items:
            return "  []"
        return "\n".join(f"  - {item}" for item in items)
    
    async def _ingest_data_sources(
        self,
        data_sources: List[Any],
        task_id: str
    ) -> int:
        """Ingest documents from data sources"""
        from runtime.retrieval.vector_store import Document
        
        ingested = 0
        
        for source in data_sources:
            if isinstance(source, str):
                # File path or URL
                if os.path.exists(source):
                    try:
                        with open(source, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        doc = Document(
                            doc_id=f"{task_id}_{ingested}",
                            content=content,
                            source=source,
                            metadata={"task_id": task_id, "type": "file"}
                        )
                        self.vector_store.add_documents([doc])
                        ingested += 1
                    except Exception:
                        pass
            
            elif isinstance(source, dict):
                # Structured source
                content = source.get("content") or source.get("text") or str(source)
                doc = Document(
                    doc_id=f"{task_id}_{ingested}",
                    content=content,
                    source=source.get("source", "inline"),
                    metadata={
                        "task_id": task_id,
                        "type": source.get("type", "inline"),
                        **source.get("metadata", {})
                    }
                )
                self.vector_store.add_documents([doc])
                ingested += 1
        
        return ingested
    
    async def _ingest_documents(
        self,
        documents: List[Any],
        task_id: str
    ) -> int:
        """Ingest a list of documents"""
        from runtime.retrieval.vector_store import Document
        
        ingested = 0
        
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
                doc_id=f"{task_id}_doc_{i}",
                content=content,
                source=source,
                metadata={"task_id": task_id, **metadata}
            )
            self.vector_store.add_documents([doc])
            ingested += 1
        
        return ingested
    
    async def _ingest_inline_content(
        self,
        content: Any,
        task_id: str
    ) -> int:
        """Ingest inline content"""
        from runtime.retrieval.vector_store import Document
        
        if isinstance(content, str):
            text = content
        elif isinstance(content, dict):
            text = json.dumps(content, ensure_ascii=False)
        elif isinstance(content, list):
            text = "\n".join(str(item) for item in content)
        else:
            text = str(content)
        
        # Chunk content if too long
        chunks = self._chunk_content(text, max_length=1000)
        
        for i, chunk in enumerate(chunks):
            doc = Document(
                doc_id=f"{task_id}_chunk_{i}",
                content=chunk,
                source="inline",
                chunk_index=i,
                metadata={"task_id": task_id, "type": "inline", "chunk": i}
            )
            self.vector_store.add_documents([doc])
        
        return len(chunks)
    
    def _chunk_content(self, text: str, max_length: int = 1000) -> List[str]:
        """Chunk content into smaller pieces"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        sentences = text.split(". ")
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text[:max_length]]
    
    async def _generate_output(
        self,
        query: str,
        evidence: List[Dict[str, Any]],
        context: Dict[str, Any],
        task_id: str
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Generate output using LLM with evidence"""
        try:
            prompt_data = self.prompt_loader.load_prompt("execution", "generator", "v1")
        except Exception:
            # Fallback prompt
            prompt_data = {
                "system_prompt": "You are a helpful assistant. Answer based on the provided evidence.",
                "user_prompt_template": "Evidence:\n{evidence}\n\nQuestion: {query}\n\nAnswer:",
                "json_schema": {"type": "object", "properties": {"answer": {"type": "string"}}}
            }
        
        # Format evidence
        evidence_text = "\n\n".join(
            f"[{i+1}] {e.get('content', '')[:500]}"
            for i, e in enumerate(evidence[:5])
        )
        
        user_prompt = prompt_data.get("user_prompt_template", "{evidence}\n{query}").format(
            evidence=evidence_text,
            query=query
        )
        
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data.get("system_prompt", ""),
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=context.get("tenant_id", "default")
        )
        
        output = result.get("answer") or result.get("output") or str(result)
        
        return output, meta
    
    async def _generate_manifest(
        self,
        task_id: str,
        spec: Dict[str, Any],
        artifacts: Dict[str, Any],
        evidence_count: int,
        output: Optional[str]
    ) -> Dict[str, Any]:
        """Generate delivery manifest"""
        manifest = {
            "task_id": task_id,
            "spec_summary": {
                "project_name": spec.get("project_name", "rag_project"),
                "data_sources_count": len(spec.get("data_sources", [])),
                "query": spec.get("query", "")[:100]
            },
            "artifacts": artifacts,
            "evidence_count": evidence_count,
            "output_generated": output is not None,
            "generated_at": datetime.now().isoformat()
        }
        
        manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False)
        
        result = await self.tool_dispatcher.execute(
            "file_write",
            {
                "path": f"artifacts/rag_project/{task_id}/manifest.json",
                "content": manifest_content
            },
            task_id
        )
        
        return {
            "tool": "file_write_manifest",
            "success": result.success,
            "output": result.output,
            "error": result.error
        }
    
    def get_governing_question(self) -> str:
        return "如何将意图实现为可运行软件？如何构建 RAG 系统？"
