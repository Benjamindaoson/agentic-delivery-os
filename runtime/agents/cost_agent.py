"""
Cost Agent: 是否继续？预算是否允许？
Real implementation with:
- Real-time cost tracking
- Budget enforcement
- Cost projection
- Path pruning decisions
- Cost efficiency analysis
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime
import json
import os
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader


class CostBreakdown:
    """Detailed cost breakdown"""
    
    def __init__(
        self,
        llm_cost: float = 0.0,
        retrieval_cost: float = 0.0,
        storage_cost: float = 0.0,
        compute_cost: float = 0.0,
        other_cost: float = 0.0
    ):
        self.llm_cost = llm_cost
        self.retrieval_cost = retrieval_cost
        self.storage_cost = storage_cost
        self.compute_cost = compute_cost
        self.other_cost = other_cost
    
    @property
    def total(self) -> float:
        return (
            self.llm_cost +
            self.retrieval_cost +
            self.storage_cost +
            self.compute_cost +
            self.other_cost
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "llm_cost": self.llm_cost,
            "retrieval_cost": self.retrieval_cost,
            "storage_cost": self.storage_cost,
            "compute_cost": self.compute_cost,
            "other_cost": self.other_cost,
            "total": self.total
        }


class CostProjection:
    """Cost projection for remaining execution"""
    
    def __init__(
        self,
        current_cost: float,
        projected_total: float,
        budget_remaining: float,
        will_exceed_budget: bool,
        confidence: float = 0.8
    ):
        self.current_cost = current_cost
        self.projected_total = projected_total
        self.budget_remaining = budget_remaining
        self.will_exceed_budget = will_exceed_budget
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_cost": self.current_cost,
            "projected_total": self.projected_total,
            "budget_remaining": self.budget_remaining,
            "will_exceed_budget": self.will_exceed_budget,
            "confidence": self.confidence
        }


class CostDecision:
    """Cost-based decision"""
    
    CONTINUE = "continue"
    DEGRADE = "degrade"
    TERMINATE = "terminate"
    
    def __init__(
        self,
        action: str,
        reason: str,
        cost_usage: float,
        budget_remaining: float,
        budget_utilization: float,
        projection: Optional[CostProjection] = None,
        breakdown: Optional[CostBreakdown] = None,
        flags: List[str] = None,
        recommendations: List[str] = None
    ):
        self.action = action
        self.reason = reason
        self.cost_usage = cost_usage
        self.budget_remaining = budget_remaining
        self.budget_utilization = budget_utilization
        self.projection = projection
        self.breakdown = breakdown
        self.flags = flags or []
        self.recommendations = recommendations or []
        self.decided_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "cost_usage": self.cost_usage,
            "budget_remaining": self.budget_remaining,
            "budget_utilization": self.budget_utilization,
            "projection": self.projection.to_dict() if self.projection else None,
            "breakdown": self.breakdown.to_dict() if self.breakdown else None,
            "flags": self.flags,
            "recommendations": self.recommendations,
            "decided_at": self.decided_at
        }


class CostTracker:
    """Tracks costs from various sources"""
    
    def __init__(self, artifact_base: str = "artifacts/rag_project"):
        self.artifact_base = artifact_base
    
    def get_task_costs(self, task_id: str) -> CostBreakdown:
        """Get cost breakdown for a task from artifacts"""
        breakdown = CostBreakdown()
        
        # Try to load cost report
        cost_path = os.path.join(self.artifact_base, task_id, "cost_report.json")
        if os.path.exists(cost_path):
            try:
                with open(cost_path, "r", encoding="utf-8") as f:
                    cost_entries = json.load(f) or []
                    for entry in cost_entries:
                        cost = entry.get("estimated_cost", 0.0)
                        provider = entry.get("provider", "").lower()
                        
                        if "llm" in provider or "qwen" in provider or "openai" in provider:
                            breakdown.llm_cost += cost
                        else:
                            breakdown.other_cost += cost
            except Exception:
                pass
        
        return breakdown
    
    def get_historical_costs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical cost data for projection"""
        costs = []
        
        if not os.path.exists(self.artifact_base):
            return costs
        
        for task_dir in os.listdir(self.artifact_base)[:limit]:
            cost_path = os.path.join(self.artifact_base, task_dir, "cost_report.json")
            if os.path.exists(cost_path):
                try:
                    with open(cost_path, "r", encoding="utf-8") as f:
                        entries = json.load(f) or []
                        total = sum(e.get("estimated_cost", 0.0) for e in entries)
                        costs.append({
                            "task_id": task_dir,
                            "total_cost": total
                        })
                except Exception:
                    continue
        
        return costs


class CostAgent(BaseAgent):
    """
    Industrial Cost Agent implementation.
    
    Responsibilities:
    - Real-time cost tracking
    - Budget enforcement (tenant-aware)
    - Concurrency-aware cost projection
    - DAG degradation decisions
    - Cost efficiency analysis
    """
    
    def __init__(self):
        super().__init__("Cost")
        self.llm_adapter = get_llm_adapter()  # Use adapter instead of raw client
        self.prompt_loader = PromptLoader()
        self.cost_tracker = CostTracker()
        
        # Default thresholds (can be overridden by config)
        self.alert_threshold = 0.8  # 80% budget usage triggers alert
        self.degrade_threshold = 0.9  # 90% triggers degraded mode
        self.terminate_threshold = 1.0  # 100% triggers termination
        
        # ROUND 3: Tenant budget controller for multi-tenant isolation
        from runtime.tenancy.tenant_budget_controller import get_tenant_budget_controller
        self.tenant_budget_controller = get_tenant_budget_controller()
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Execute cost evaluation and decision (ROUND 3: Tenant-aware + Concurrency-aware).
        
        Workflow:
        1. Check tenant budget (multi-tenant isolation)
        2. Collect current costs from artifacts
        3. Calculate budget utilization (including concurrent runs)
        4. Project remaining costs
        5. Make continue/degrade/terminate decision
        6. DAG degradation if necessary
        7. Generate cost flags and recommendations
        """
        # ROUND 3: Get tenant_id for multi-tenant isolation
        tenant_id = context.get("tenant_id", "default")
        
        # ROUND 3: Check tenant budget status
        tenant_budget_usage = self.tenant_budget_controller.get_budget_usage(tenant_id)
        running_tasks = self.tenant_budget_controller.get_running_tasks(tenant_id)
        
        # Get budget configuration (tenant-aware)
        spec = context.get("spec", {})
        budget_config = context.get("budget_config", {})
        
        # ROUND 3: Use tenant budget limit
        budget_total = float(
            tenant_budget_usage.budget_limit or
            context.get("budget_total") or
            budget_config.get("max_cost") or
            spec.get("budget", {}).get("max_cost") or
            1000.0
        )
        
        # ROUND 3: Get current cost usage (tenant-aware, includes all concurrent runs)
        cost_usage_current_task = context.get("cost_usage", 0.0)
        
        if cost_usage_current_task == 0.0:
            # Calculate from artifacts
            breakdown = self.cost_tracker.get_task_costs(task_id)
            cost_usage_current_task = breakdown.total
        else:
            breakdown = CostBreakdown(other_cost=cost_usage_current_task)
        
        # ROUND 3: Account for concurrent runs (multi-tenant aware)
        cost_usage_tenant_total = tenant_budget_usage.current_usage
        
        # Calculate budget remaining and utilization (tenant-level)
        budget_remaining = max(0, budget_total - cost_usage_tenant_total)
        budget_utilization = cost_usage_tenant_total / budget_total if budget_total > 0 else 0.0
        
        # ROUND 3: Concurrency factor (affects risk assessment)
        concurrency_factor = tenant_budget_usage.concurrent_runs / max(tenant_budget_usage.max_concurrent_runs, 1)
        
        # ROUND 3: Project costs (concurrency-aware)
        projection = self._project_costs_concurrent(
            current_cost_task=cost_usage_current_task,
            current_cost_tenant=cost_usage_tenant_total,
            budget_total=budget_total,
            concurrent_runs=tenant_budget_usage.concurrent_runs,
            context=context
        )
        
        # ROUND 3: Make decision based on thresholds + concurrency
        decision = self._make_decision(
            cost_usage=cost_usage_tenant_total,
            budget_remaining=budget_remaining,
            budget_utilization=budget_utilization,
            projection=projection,
            breakdown=breakdown,
            context=context,
            concurrency_factor=concurrency_factor
        )
        
        # ROUND 3: If decision is DEGRADE, determine DAG modifications
        dag_degradation = None
        if decision.action == CostDecision.DEGRADE:
            dag_degradation = self._compute_dag_degradation(
                context=context,
                budget_remaining=budget_remaining,
                concurrency_factor=concurrency_factor
            )
        
        # Generate flags and recommendations
        flags = self._generate_flags(decision, budget_utilization, projection)
        recommendations = self._generate_recommendations(decision, budget_utilization)
        
        decision.flags = flags
        decision.recommendations = recommendations
        
        # Call LLM for additional analysis (optional)
        llm_output = None
        llm_meta = {"llm_used": False}
        
        try:
            llm_output, llm_meta = await self._call_llm_for_analysis(
                decision, task_id, context.get("tenant_id", "default")
            )
        except Exception:
            pass
        
        # Merge LLM insights
        if llm_meta.get("llm_used") and llm_output:
            if llm_output.get("cost_flags"):
                flags.extend(llm_output["cost_flags"][:3])
            if llm_output.get("recommendations"):
                recommendations.extend(llm_output["recommendations"][:3])
            if llm_output.get("decision_reason"):
                decision.reason = llm_output["decision_reason"]
        
        # Save cost artifact
        self._save_cost_artifact(task_id, decision)
        
        return {
            "decision": decision.action,
            "reason": decision.reason,
            "cost_usage": cost_usage_tenant_total,
            "cost_usage_current_task": cost_usage_current_task,
            "budget_remaining": budget_remaining,
            "budget_utilization": budget_utilization,
            "cost_breakdown": breakdown.to_dict(),
            "cost_projection": projection.to_dict() if projection else None,
            "cost_flags": flags,
            "llm_result": llm_meta,
            "dag_degradation": dag_degradation,  # ROUND 3: DAG modifications
            "tenant_id": tenant_id,  # ROUND 3: Tenant tracking
            "concurrent_runs": tenant_budget_usage.concurrent_runs,  # ROUND 3: Concurrency tracking
            "state_update": {
                "cost_agent_executed": True,
                "cost_usage": cost_usage_tenant_total,
                "cost_usage_current_task": cost_usage_current_task,
                "budget_remaining": budget_remaining,
                "budget_utilization": budget_utilization,
                "cost_flags": flags,
                "cost_decision": decision.action,
                "dag_degradation": dag_degradation,
                "tenant_id": tenant_id,
                "concurrent_runs": tenant_budget_usage.concurrent_runs,
                "concurrency_factor": concurrency_factor
            }
        }
    
    def _project_costs(
        self,
        current_cost: float,
        budget_total: float,
        context: Dict[str, Any]
    ) -> CostProjection:
        """Project total costs based on progress"""
        
        # Estimate completion percentage
        agent_count = sum([
            context.get("product_agent_executed", False),
            context.get("data_agent_executed", False),
            context.get("execution_agent_executed", False),
        ])
        total_agents = 5  # Product, Data, Execution, Evaluation, Cost
        completion_pct = (agent_count + 1) / total_agents  # +1 for current Cost agent
        
        if completion_pct > 0:
            projected_total = current_cost / completion_pct
        else:
            projected_total = current_cost * 2  # Conservative estimate
        
        budget_remaining = budget_total - current_cost
        will_exceed = projected_total > budget_total
        
        # Confidence based on completion percentage
        confidence = min(0.95, 0.5 + (completion_pct * 0.5))
        
        return CostProjection(
            current_cost=current_cost,
            projected_total=projected_total,
            budget_remaining=budget_remaining,
            will_exceed_budget=will_exceed,
            confidence=confidence
        )
    
    def _project_costs_concurrent(
        self,
        current_cost_task: float,
        current_cost_tenant: float,
        budget_total: float,
        concurrent_runs: int,
        context: Dict[str, Any]
    ) -> CostProjection:
        """
        ROUND 3: Concurrency-aware cost projection
        
        Considers:
        - Current task progress
        - Other concurrent runs
        - Tenant-level budget
        """
        # Estimate current task completion
        agent_count = sum([
            context.get("product_agent_executed", False),
            context.get("data_agent_executed", False),
            context.get("execution_agent_executed", False),
        ])
        total_agents = 5
        completion_pct = (agent_count + 1) / total_agents
        
        # Project current task total cost
        if completion_pct > 0:
            projected_task_cost = current_cost_task / completion_pct
        else:
            projected_task_cost = current_cost_task * 2
        
        # Estimate cost from other concurrent runs (assume 50% completion on average)
        cost_from_other_runs = current_cost_tenant - current_cost_task
        if concurrent_runs > 1:
            # Assume other runs will double their current cost (conservative)
            projected_other_runs_cost = cost_from_other_runs * 2
        else:
            projected_other_runs_cost = cost_from_other_runs
        
        # Total projected cost (tenant-level)
        projected_total = projected_task_cost + projected_other_runs_cost
        
        budget_remaining = budget_total - current_cost_tenant
        will_exceed = projected_total > budget_total
        
        # Confidence decreases with more concurrent runs
        base_confidence = min(0.95, 0.5 + (completion_pct * 0.5))
        concurrency_penalty = min(0.3, (concurrent_runs - 1) * 0.1)
        confidence = max(0.3, base_confidence - concurrency_penalty)
        
        return CostProjection(
            current_cost=current_cost_tenant,
            projected_total=projected_total,
            budget_remaining=budget_remaining,
            will_exceed_budget=will_exceed,
            confidence=confidence
        )
    
    def _compute_dag_degradation(
        self,
        context: Dict[str, Any],
        budget_remaining: float,
        concurrency_factor: float
    ) -> Dict[str, Any]:
        """
        ROUND 3: Compute DAG degradation strategy
        
        Returns suggestions for:
        - Nodes to skip (non-critical)
        - Nodes to merge (reduce overhead)
        - Parameter downgrades (reduce cost per node)
        """
        degradation = {
            "action": "degrade",
            "reason": "Cost + concurrency pressure",
            "modifications": []
        }
        
        # Strategy 1: Skip non-critical nodes
        if budget_remaining < 10.0 or concurrency_factor > 0.8:
            degradation["modifications"].append({
                "type": "skip_nodes",
                "nodes": ["candidate_generation_extra", "advanced_reranking"],
                "reason": "Budget critical, skip non-essential steps"
            })
        
        # Strategy 2: Reduce generation candidates
        if budget_remaining < 50.0:
            degradation["modifications"].append({
                "type": "downgrade_params",
                "target": "generation",
                "changes": {
                    "num_candidates": 1,  # Reduce from 3 to 1
                    "temperature": 0.7  # Lower temperature
                },
                "reason": "Reduce generation cost"
            })
        
        # Strategy 3: Reduce retrieval depth
        degradation["modifications"].append({
            "type": "downgrade_params",
            "target": "retrieval",
            "changes": {
                "top_k": 3,  # Reduce from 5 to 3
                "rerank": False  # Skip reranking
            },
            "reason": "Reduce retrieval overhead"
        })
        
        # Strategy 4: Use cheaper LLM models
        if concurrency_factor > 0.7:
            degradation["modifications"].append({
                "type": "switch_model",
                "target": "llm",
                "changes": {
                    "model": "qwen-fast"  # Use faster/cheaper model
                },
                "reason": "High concurrency, use cheaper model"
            })
        
        return degradation
    
    def _make_decision(
        self,
        cost_usage: float,
        budget_remaining: float,
        budget_utilization: float,
        projection: CostProjection,
        breakdown: CostBreakdown,
        context: Dict[str, Any],
        concurrency_factor: float = 0.0  # ROUND 3: New parameter
    ) -> CostDecision:
        """Make cost-based decision"""
        
        # Terminate if budget exceeded
        if budget_remaining <= 0 or budget_utilization >= self.terminate_threshold:
            return CostDecision(
                action=CostDecision.TERMINATE,
                reason=f"预算已耗尽 (使用率: {budget_utilization:.1%})",
                cost_usage=cost_usage,
                budget_remaining=budget_remaining,
                budget_utilization=budget_utilization,
                projection=projection,
                breakdown=breakdown
            )
        
        # ROUND 3: Degrade if approaching limit OR high concurrency
        if budget_utilization >= self.degrade_threshold or concurrency_factor >= 0.8:
            reason_parts = []
            if budget_utilization >= self.degrade_threshold:
                reason_parts.append(f"接近预算上限 (使用率: {budget_utilization:.1%})")
            if concurrency_factor >= 0.8:
                reason_parts.append(f"高并发压力 (并发度: {concurrency_factor:.1%})")
            
            return CostDecision(
                action=CostDecision.DEGRADE,
                reason=f"{' + '.join(reason_parts)}，启用降级模式",
                cost_usage=cost_usage,
                budget_remaining=budget_remaining,
                budget_utilization=budget_utilization,
                projection=projection,
                breakdown=breakdown
            )
        
        # Check projection
        if projection and projection.will_exceed_budget:
            return CostDecision(
                action=CostDecision.DEGRADE,
                reason=f"预测将超出预算 (预计: {projection.projected_total:.2f})",
                cost_usage=cost_usage,
                budget_remaining=budget_remaining,
                budget_utilization=budget_utilization,
                projection=projection,
                breakdown=breakdown
            )
        
        # Continue normally
        return CostDecision(
            action=CostDecision.CONTINUE,
            reason=f"成本检查通过 (使用率: {budget_utilization:.1%}，剩余: {budget_remaining:.2f})",
            cost_usage=cost_usage,
            budget_remaining=budget_remaining,
            budget_utilization=budget_utilization,
            projection=projection,
            breakdown=breakdown
        )
    
    def _generate_flags(
        self,
        decision: CostDecision,
        budget_utilization: float,
        projection: Optional[CostProjection]
    ) -> List[str]:
        """Generate cost flags"""
        flags = []
        
        if budget_utilization >= self.alert_threshold:
            flags.append("BUDGET_ALERT")
        
        if budget_utilization >= self.degrade_threshold:
            flags.append("BUDGET_CRITICAL")
        
        if projection and projection.will_exceed_budget:
            flags.append("PROJECTED_OVERRUN")
        
        if decision.action == CostDecision.TERMINATE:
            flags.append("TERMINATED_BY_COST")
        
        if decision.action == CostDecision.DEGRADE:
            flags.append("DEGRADED_MODE")
        
        return flags
    
    def _generate_recommendations(
        self,
        decision: CostDecision,
        budget_utilization: float
    ) -> List[str]:
        """Generate cost recommendations"""
        recommendations = []
        
        if budget_utilization > 0.5:
            recommendations.append("Consider using more cost-efficient models")
        
        if budget_utilization > 0.7:
            recommendations.append("Review and optimize LLM calls")
        
        if decision.action == CostDecision.DEGRADE:
            recommendations.append("Reduce generation candidates and retrieval depth")
        
        if decision.action == CostDecision.TERMINATE:
            recommendations.append("Request budget increase or simplify task")
        
        return recommendations
    
    async def _call_llm_for_analysis(
        self,
        decision: CostDecision,
        task_id: str,
        tenant_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Call LLM for cost analysis"""
        try:
            prompt_data = self.prompt_loader.load_prompt("cost", "reasoner", "v1")
        except Exception:
            # Fallback if prompt not found
            return {}, {"llm_used": False}
        
        # Build user prompt
        user_prompt = prompt_data.get(
            "user_prompt_template",
            "Analyze cost: usage={cost_usage}, remaining={budget_remaining}, decision={decision}"
        ).format(
            cost_usage=decision.cost_usage,
            budget_remaining=decision.budget_remaining,
            decision=decision.action
        )
        
        # Use adapter instead of raw client
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data.get("system_prompt", "You are a cost analyst."),
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        return result, meta
    
    def _save_cost_artifact(self, task_id: str, decision: CostDecision):
        """Save cost decision artifact"""
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        os.makedirs(artifact_dir, exist_ok=True)
        
        cost_decision_path = os.path.join(artifact_dir, "cost_decision.json")
        with open(cost_decision_path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2, ensure_ascii=False)
    
    def get_governing_question(self) -> str:
        return "是否继续？预算是否允许？成本是否可控？"
