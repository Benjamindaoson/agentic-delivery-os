"""
Multi-Candidate Generator - Industrial-Grade Multi-Candidate Generation
L5 Core Component: Generation Layer Enhancement

Features:
- Real LLM-based candidate generation
- Multiple generation strategies
- Quality scoring integration
- Cost tracking per candidate
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import os
import uuid
import asyncio
import time

# Import LLM adapter
try:
    from runtime.llm import get_llm_adapter
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    get_llm_adapter = None


class GenerationCandidate(BaseModel):
    """Single generation candidate with full tracking"""
    candidate_id: str
    content: str
    generation_params: Dict[str, Any]
    metadata: Dict[str, Any]
    estimated_quality: float
    estimated_cost: float
    generation_latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    llm_used: bool = True
    fallback_used: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


class MultiCandidateResult(BaseModel):
    """Result of multi-candidate generation"""
    request_id: str
    query: str
    context: Dict[str, Any]
    candidates: List[GenerationCandidate]
    generation_strategy: str
    total_cost: float
    total_latency_ms: float
    created_at: datetime = Field(default_factory=datetime.now)


class MultiCandidateGenerator:
    """
    Industrial-grade multi-candidate generator.
    Generates multiple candidate responses using real LLM calls.
    """
    
    def __init__(self, artifacts_path: str = "artifacts/generation"):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Initialize LLM adapter
        self.llm_adapter = get_llm_adapter() if LLM_AVAILABLE else None
        
        # Generation strategies
        self.strategies = {
            "temperature_sampling": self._generate_temperature_variants,
            "prompt_variations": self._generate_prompt_variants,
            "model_ensemble": self._generate_model_ensemble,
            "parallel_diverse": self._generate_parallel_diverse
        }
        
        # Default prompts
        self.system_prompt = """You are a helpful AI assistant. Generate a high-quality response based on the provided context and query.
Your response should be:
- Accurate and grounded in the provided evidence
- Clear and well-structured
- Comprehensive yet concise"""
        
        self.response_schema = {
            "type": "object",
            "properties": {
                "response": {"type": "string", "description": "The generated response"},
                "confidence": {"type": "number", "description": "Confidence score 0-1"},
                "key_points": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["response"]
        }
    
    async def generate_candidates_async(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int = 3,
        strategy: str = "temperature_sampling",
        task_id: Optional[str] = None
    ) -> MultiCandidateResult:
        """
        Generate multiple candidates asynchronously using real LLM.
        
        Args:
            query: User query
            context: Generation context (documents, evidence, etc.)
            num_candidates: Number of candidates to generate
            strategy: Generation strategy
            task_id: Optional task ID for tracking
            
        Returns:
            MultiCandidateResult with all candidates
        """
        request_id = f"gen_{uuid.uuid4().hex[:16]}"
        start_time = time.time()
        
        # Select strategy
        generator_func = self.strategies.get(strategy, self._generate_temperature_variants)
        
        # Generate candidates (async)
        candidates = await generator_func(query, context, num_candidates, task_id)
        
        total_time = (time.time() - start_time) * 1000
        
        # Compute totals
        total_cost = sum(c.estimated_cost for c in candidates)
        total_latency = sum(c.generation_latency_ms for c in candidates)
        
        result = MultiCandidateResult(
            request_id=request_id,
            query=query,
            context=context,
            candidates=candidates,
            generation_strategy=strategy,
            total_cost=total_cost,
            total_latency_ms=total_latency
        )
        
        # Save result
        self._save_result(result)
        
        return result
    
    def generate_candidates(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int = 3,
        strategy: str = "temperature_sampling"
    ) -> MultiCandidateResult:
        """
        Synchronous wrapper for generate_candidates_async.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.generate_candidates_async(query, context, num_candidates, strategy)
        )
    
    async def _generate_temperature_variants(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int,
        task_id: Optional[str] = None
    ) -> List[GenerationCandidate]:
        """Generate candidates with different temperature settings using real LLM"""
        candidates = []
        temperatures = [0.2, 0.5, 0.8, 1.0][:num_candidates]
        
        for i, temp in enumerate(temperatures):
            candidate = await self._generate_single_candidate(
                query=query,
                context=context,
                temperature=temp,
                candidate_id=f"temp_{temp}_{i}",
                method="temperature_sampling",
                task_id=task_id
            )
            candidates.append(candidate)
        
        return candidates
    
    async def _generate_prompt_variants(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int,
        task_id: Optional[str] = None
    ) -> List[GenerationCandidate]:
        """Generate candidates with different prompt styles"""
        candidates = []
        
        prompt_styles = {
            "concise": "Be brief and direct. Provide a concise answer.",
            "detailed": "Provide a comprehensive, detailed answer with examples.",
            "analytical": "Analyze the question systematically. Consider multiple perspectives.",
            "step_by_step": "Break down your answer into clear steps or points."
        }
        
        styles = list(prompt_styles.items())[:num_candidates]
        
        for i, (style_name, style_instruction) in enumerate(styles):
            # Modify system prompt based on style
            styled_system = f"{self.system_prompt}\n\nStyle instruction: {style_instruction}"
            
            candidate = await self._generate_single_candidate(
                query=query,
                context=context,
                temperature=0.7,
                candidate_id=f"prompt_{style_name}_{i}",
                method="prompt_variations",
                system_prompt_override=styled_system,
                extra_metadata={"style": style_name},
                task_id=task_id
            )
            candidates.append(candidate)
        
        return candidates
    
    async def _generate_model_ensemble(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int,
        task_id: Optional[str] = None
    ) -> List[GenerationCandidate]:
        """Generate candidates using different model configurations"""
        candidates = []
        
        # Different model configs (in practice, these would be different models)
        configs = [
            {"temperature": 0.3, "max_tokens": 256, "name": "fast"},
            {"temperature": 0.5, "max_tokens": 512, "name": "balanced"},
            {"temperature": 0.7, "max_tokens": 1024, "name": "quality"}
        ][:num_candidates]
        
        for i, config in enumerate(configs):
            candidate = await self._generate_single_candidate(
                query=query,
                context=context,
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                candidate_id=f"model_{config['name']}_{i}",
                method="model_ensemble",
                extra_metadata={"model_config": config["name"]},
                task_id=task_id
            )
            candidates.append(candidate)
        
        return candidates
    
    async def _generate_parallel_diverse(
        self,
        query: str,
        context: Dict[str, Any],
        num_candidates: int,
        task_id: Optional[str] = None
    ) -> List[GenerationCandidate]:
        """Generate diverse candidates in parallel"""
        # Create tasks for parallel generation
        tasks = []
        for i in range(num_candidates):
            temp = 0.3 + (i * 0.3)  # Varying temperatures
            task = self._generate_single_candidate(
                query=query,
                context=context,
                temperature=min(temp, 1.0),
                candidate_id=f"diverse_{i}",
                method="parallel_diverse",
                task_id=task_id
            )
            tasks.append(task)
        
        # Execute in parallel
        candidates = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_candidates = [c for c in candidates if isinstance(c, GenerationCandidate)]
        return valid_candidates
    
    async def _generate_single_candidate(
        self,
        query: str,
        context: Dict[str, Any],
        temperature: float,
        candidate_id: str,
        method: str,
        max_tokens: int = 512,
        system_prompt_override: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> GenerationCandidate:
        """Generate a single candidate using real LLM"""
        start_time = time.time()
        
        # Format context for the prompt
        context_text = self._format_context(context)
        
        user_prompt = f"""Context:
{context_text}

Query: {query}

Please provide a high-quality response based on the context above."""
        
        system_prompt = system_prompt_override or self.system_prompt
        
        # Call LLM
        content = ""
        estimated_quality = 0.5
        estimated_cost = 0.0
        input_tokens = 0
        output_tokens = 0
        llm_used = True
        fallback_used = False
        
        if self.llm_adapter:
            try:
                result, meta = await self.llm_adapter.call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=self.response_schema,
                    meta={"temperature": temperature, "max_tokens": max_tokens},
                    task_id=task_id
                )
                
                # Extract response
                if result:
                    content = result.get("response", "")
                    estimated_quality = result.get("confidence", 0.7)
                
                # Extract cost info
                estimated_cost = meta.get("cost", 0.0)
                input_tokens = meta.get("input_tokens", 0)
                output_tokens = meta.get("output_tokens", 0)
                llm_used = meta.get("llm_used", True)
                fallback_used = meta.get("fallback_used", False)
                
            except Exception as e:
                # Fallback response
                content = f"[Generation failed: {str(e)[:100]}]"
                estimated_quality = 0.0
                fallback_used = True
        else:
            # No LLM available - generate placeholder
            content = self._generate_fallback_response(query, context, temperature)
            llm_used = False
        
        latency_ms = (time.time() - start_time) * 1000
        
        metadata = {
            "method": method,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        
        return GenerationCandidate(
            candidate_id=candidate_id,
            content=content,
            generation_params={"temperature": temperature, "max_tokens": max_tokens},
            metadata=metadata,
            estimated_quality=estimated_quality,
            estimated_cost=estimated_cost,
            generation_latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            llm_used=llm_used,
            fallback_used=fallback_used
        )
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt"""
        parts = []
        
        if "documents" in context:
            for i, doc in enumerate(context["documents"][:5]):
                if isinstance(doc, dict):
                    text = doc.get("content", doc.get("text", str(doc)))
                else:
                    text = str(doc)
                parts.append(f"[Document {i+1}]: {text[:500]}")
        
        if "evidence" in context:
            for i, ev in enumerate(context["evidence"][:3]):
                if isinstance(ev, dict):
                    text = ev.get("content", str(ev))
                else:
                    text = str(ev)
                parts.append(f"[Evidence {i+1}]: {text[:300]}")
        
        return "\n\n".join(parts) if parts else "No context provided."
    
    def _generate_fallback_response(
        self,
        query: str,
        context: Dict[str, Any],
        temperature: float
    ) -> str:
        """Generate fallback response when LLM is unavailable"""
        doc_count = len(context.get("documents", []))
        evidence_count = len(context.get("evidence", []))
        
        response = f"[Fallback Response for: {query[:100]}]\n\n"
        response += f"Based on {doc_count} documents and {evidence_count} evidence items.\n"
        response += f"(Temperature: {temperature}, LLM unavailable)"
        
        return response
    
    def _save_result(self, result: MultiCandidateResult):
        """Save generation result to artifacts"""
        path = os.path.join(self.artifacts_path, f"{result.request_id}.json")
        with open(path, 'w') as f:
            f.write(result.model_dump_json(indent=2))


# Singleton instance
_generator = None

def get_generator() -> MultiCandidateGenerator:
    """Get singleton MultiCandidateGenerator instance"""
    global _generator
    if _generator is None:
        _generator = MultiCandidateGenerator()
    return _generator



