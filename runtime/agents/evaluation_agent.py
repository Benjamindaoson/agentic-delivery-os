"""
Evaluation Agent: 是否完成？是否达到成功标准？
Real implementation with:
- Evidence-based quality scoring
- Grounding verification
- Latency tracking
- Failure attribution
- Regression detection
"""
from runtime.agents.base_agent import BaseAgent
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime
import json
import os
import hashlib
from runtime.llm import get_llm_adapter
from runtime.llm.prompt_loader import PromptLoader


class QualityMetrics:
    """Quality metrics for evaluation"""
    
    def __init__(
        self,
        completeness_score: float = 0.0,
        accuracy_score: float = 0.0,
        grounding_score: float = 0.0,
        coherence_score: float = 0.0,
        latency_score: float = 0.0,
        cost_efficiency_score: float = 0.0
    ):
        self.completeness_score = completeness_score
        self.accuracy_score = accuracy_score
        self.grounding_score = grounding_score
        self.coherence_score = coherence_score
        self.latency_score = latency_score
        self.cost_efficiency_score = cost_efficiency_score
    
    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score"""
        weights = {
            "completeness": 0.20,
            "accuracy": 0.25,
            "grounding": 0.25,
            "coherence": 0.15,
            "latency": 0.10,
            "cost_efficiency": 0.05
        }
        
        return (
            self.completeness_score * weights["completeness"] +
            self.accuracy_score * weights["accuracy"] +
            self.grounding_score * weights["grounding"] +
            self.coherence_score * weights["coherence"] +
            self.latency_score * weights["latency"] +
            self.cost_efficiency_score * weights["cost_efficiency"]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "completeness_score": self.completeness_score,
            "accuracy_score": self.accuracy_score,
            "grounding_score": self.grounding_score,
            "coherence_score": self.coherence_score,
            "latency_score": self.latency_score,
            "cost_efficiency_score": self.cost_efficiency_score,
            "overall_score": self.overall_score
        }


class EvaluationResult:
    """Complete evaluation result"""
    
    def __init__(
        self,
        task_id: str,
        passed: bool,
        quality_score: float,
        metrics: QualityMetrics,
        grounded_rate: float = 1.0,
        latency_ms: float = 0.0,
        failure_type: Optional[str] = None,
        blame_hint: Optional[str] = None,
        issues: List[str] = None,
        recommendations: List[str] = None
    ):
        self.task_id = task_id
        self.passed = passed
        self.quality_score = quality_score
        self.metrics = metrics
        self.grounded_rate = grounded_rate
        self.latency_ms = latency_ms
        self.failure_type = failure_type
        self.blame_hint = blame_hint
        self.issues = issues or []
        self.recommendations = recommendations or []
        self.evaluated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "quality_score": self.quality_score,
            "metrics": self.metrics.to_dict(),
            "grounded_rate": self.grounded_rate,
            "latency_ms": self.latency_ms,
            "failure_type": self.failure_type,
            "blame_hint": self.blame_hint,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "evaluated_at": self.evaluated_at
        }


class GroundingVerifier:
    """Verifies that outputs are grounded in evidence"""
    
    @classmethod
    def verify(
        cls,
        output: str,
        evidence: List[Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        """
        Verify output grounding in evidence.
        
        Returns:
            Tuple of (grounding_score, issues)
        """
        if not output or not evidence:
            return 0.0, ["No output or evidence to verify"]
        
        issues = []
        grounded_claims = 0
        total_claims = 0
        
        # Extract sentences/claims from output
        sentences = [s.strip() for s in output.split('.') if s.strip()]
        
        # Build evidence text corpus
        evidence_text = " ".join(
            e.get("content", "") for e in evidence
        ).lower()
        evidence_words = set(evidence_text.split())
        
        for sentence in sentences:
            if len(sentence.split()) < 3:
                continue  # Skip very short sentences
            
            total_claims += 1
            sentence_words = set(sentence.lower().split())
            
            # Check word overlap with evidence
            overlap = len(sentence_words & evidence_words)
            overlap_ratio = overlap / max(len(sentence_words), 1)
            
            if overlap_ratio > 0.3:  # 30% word overlap threshold
                grounded_claims += 1
            else:
                # Check for semantic similarity (simplified)
                key_words = [w for w in sentence_words if len(w) > 4]
                key_overlap = len(set(key_words) & evidence_words)
                if key_overlap >= 1:
                    grounded_claims += 0.5
                else:
                    issues.append(f"Possibly ungrounded: '{sentence[:50]}...'")
        
        if total_claims == 0:
            return 1.0, []  # No claims to verify
        
        grounding_score = grounded_claims / total_claims
        return min(1.0, grounding_score), issues


class RegressionDetector:
    """Detects quality regressions compared to historical results"""
    
    def __init__(self, eval_path: str = "artifacts/eval"):
        self.eval_path = eval_path
    
    def detect_regression(
        self,
        current_score: float,
        task_type: str,
        threshold: float = 0.05
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect if current score represents a regression.
        
        Returns:
            Tuple of (is_regression, details)
        """
        if not os.path.exists(self.eval_path):
            return False, {"reason": "No historical data"}
        
        # Collect historical scores
        historical_scores = []
        
        for file in os.listdir(self.eval_path):
            if not file.endswith(".json"):
                continue
            
            try:
                with open(os.path.join(self.eval_path, file), "r") as f:
                    data = json.load(f)
                    if data.get("task_type") == task_type:
                        historical_scores.append(data.get("quality_score", 0))
            except Exception:
                continue
        
        if len(historical_scores) < 3:
            return False, {"reason": "Insufficient historical data"}
        
        # Calculate baseline
        avg_score = sum(historical_scores) / len(historical_scores)
        regression_threshold = avg_score * (1 - threshold)
        
        is_regression = current_score < regression_threshold
        
        return is_regression, {
            "avg_historical": avg_score,
            "current": current_score,
            "threshold": regression_threshold,
            "sample_size": len(historical_scores)
        }


class EvaluationAgent(BaseAgent):
    """
    Real Evaluation Agent implementation.
    
    Responsibilities:
    - Quality scoring with multiple dimensions
    - Grounding verification
    - Latency and cost efficiency tracking
    - Failure attribution
    - Regression detection
    """
    
    def __init__(self):
        super().__init__("Evaluation")
        self.llm_adapter = get_llm_adapter()
        self.prompt_loader = PromptLoader()
        self.grounding_verifier = GroundingVerifier()
        self.regression_detector = RegressionDetector()
        self.quality_gate = 0.7  # Minimum quality score to pass
    
    async def execute(self, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Execute comprehensive evaluation.
        
        Workflow:
        1. Collect execution metrics
        2. Calculate quality scores
        3. Verify grounding
        4. Detect regressions
        5. Attribute failures
        6. Generate recommendations
        """
        import time
        start_time = time.time()
        
        # Extract context information
        spec = context.get("spec", {})
        execution_result = context.get("execution_result", {})
        data_manifest = context.get("data_manifest", {})
        evidence = context.get("evidence", [])
        output = context.get("output", "")
        
        # Agent execution status
        product_executed = context.get("product_agent_executed", False)
        data_executed = context.get("data_agent_executed", False)
        execution_executed = context.get("execution_agent_executed", False)
        
        # Cost and latency from context
        cost_usage = context.get("cost_usage", 0.0)
        budget_total = context.get("budget_remaining", 1000.0) + cost_usage
        
        # Calculate quality metrics
        metrics = self._calculate_metrics(
            context=context,
            spec=spec,
            execution_result=execution_result,
            data_manifest=data_manifest,
            evidence=evidence,
            output=output,
            cost_usage=cost_usage,
            budget_total=budget_total
        )
        
        # Verify grounding
        grounding_score = 1.0
        grounding_issues = []
        if output and evidence:
            grounding_score, grounding_issues = self.grounding_verifier.verify(
                output, evidence
            )
            metrics.grounding_score = grounding_score
        
        # Calculate overall quality score
        quality_score = metrics.overall_score
        
        # Determine pass/fail
        issues = []
        passed = True
        failure_type = None
        blame_hint = None
        
        # Check critical failures
        if not product_executed:
            passed = False
            failure_type = "execution_issue"
            blame_hint = "Product Agent"
            issues.append("Product Agent did not execute")
        
        if not data_executed:
            passed = False
            failure_type = "data_issue"
            blame_hint = "Data Agent"
            issues.append("Data Agent did not execute")
        
        if not execution_executed:
            passed = False
            failure_type = "execution_issue"
            blame_hint = "Execution Agent"
            issues.append("Execution Agent did not execute")
        
        # Check artifacts
        artifacts = context.get("artifacts", {})
        if not artifacts.get("config_generated", False):
            passed = False
            failure_type = "execution_issue"
            blame_hint = "Execution Agent"
            issues.append("Config not generated")
        
        # Check quality gate
        if quality_score < self.quality_gate:
            passed = False
            failure_type = "evaluation_issue"
            blame_hint = "Quality below threshold"
            issues.append(f"Quality score {quality_score:.2f} below threshold {self.quality_gate}")
        
        # Check grounding
        if grounding_score < 0.5:
            issues.append(f"Low grounding score: {grounding_score:.2f}")
            issues.extend(grounding_issues[:3])
        
        # Detect regression
        task_type = context.get("task_type", "general")
        is_regression, regression_details = self.regression_detector.detect_regression(
            quality_score, task_type
        )
        if is_regression:
            issues.append(f"Quality regression detected: {regression_details}")
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            passed=passed,
            metrics=metrics,
            issues=issues,
            context=context
        )
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        
        # Build evaluation result
        eval_result = EvaluationResult(
            task_id=task_id,
            passed=passed,
            quality_score=quality_score,
            metrics=metrics,
            grounded_rate=grounding_score,
            latency_ms=latency_ms,
            failure_type=failure_type,
            blame_hint=blame_hint,
            issues=issues,
            recommendations=recommendations
        )
        
        # Call LLM for additional insights (optional)
        llm_output = None
        llm_meta = {"llm_used": False}
        
        try:
            llm_output, llm_meta = await self._call_llm_for_review(
                eval_result, task_id, context.get("tenant_id", "default")
            )
        except Exception:
            pass
        
        # Merge LLM insights if available
        if llm_meta.get("llm_used") and llm_output:
            if llm_output.get("additional_issues"):
                issues.extend(llm_output["additional_issues"][:3])
            if llm_output.get("additional_recommendations"):
                recommendations.extend(llm_output["additional_recommendations"][:3])
        
        # Save evaluation artifact
        self._save_evaluation_artifact(task_id, eval_result, llm_output)
        
        # Determine decision
        decision = "passed" if passed else "failed"
        reason = f"质量评测{'通过' if passed else '失败'} (分数: {quality_score:.2f})"
        if issues:
            reason += f" 问题: {'; '.join(issues[:2])}"
        
        return {
            "decision": decision,
            "reason": reason,
            "evaluation_result": eval_result.to_dict(),
            "llm_result": llm_meta,
            "state_update": {
                "evaluation_agent_executed": True,
                "evaluation_result": {
                    "quality_score": quality_score,
                    "passed": passed,
                    "grounded_rate": grounding_score
                },
                "last_evaluation_failed": not passed,
                "last_failure_type": failure_type,
                "last_blame_hint": blame_hint
            }
        }
    
    def _calculate_metrics(
        self,
        context: Dict[str, Any],
        spec: Dict[str, Any],
        execution_result: Dict[str, Any],
        data_manifest: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        output: str,
        cost_usage: float,
        budget_total: float
    ) -> QualityMetrics:
        """Calculate quality metrics"""
        
        # Completeness: Did we generate all expected artifacts?
        expected_artifacts = ["config_generated"]
        artifacts = context.get("artifacts", {})
        generated_count = sum(1 for a in expected_artifacts if artifacts.get(a, False))
        completeness_score = generated_count / max(len(expected_artifacts), 1)
        
        # Accuracy: Data quality and validation
        if data_manifest:
            accuracy_score = data_manifest.get("quality_score", 0.8)
        else:
            accuracy_score = 0.8  # Default
        
        # Grounding: Will be updated by grounding verifier
        grounding_score = 1.0 if evidence else 0.5
        
        # Coherence: Check if execution was coherent
        agent_count = sum([
            context.get("product_agent_executed", False),
            context.get("data_agent_executed", False),
            context.get("execution_agent_executed", False)
        ])
        coherence_score = agent_count / 3.0
        
        # Latency score (inversely proportional to time)
        # Assume target latency is 5000ms
        total_latency = context.get("total_latency_ms", 1000)
        latency_score = max(0, min(1.0, 1.0 - (total_latency - 1000) / 10000))
        
        # Cost efficiency
        if budget_total > 0:
            cost_ratio = cost_usage / budget_total
            cost_efficiency_score = max(0, 1.0 - cost_ratio)
        else:
            cost_efficiency_score = 1.0
        
        return QualityMetrics(
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            grounding_score=grounding_score,
            coherence_score=coherence_score,
            latency_score=latency_score,
            cost_efficiency_score=cost_efficiency_score
        )
    
    def _generate_recommendations(
        self,
        passed: bool,
        metrics: QualityMetrics,
        issues: List[str],
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on evaluation"""
        recommendations = []
        
        if not passed:
            recommendations.append("Review and fix identified issues before proceeding")
        
        if metrics.completeness_score < 0.8:
            recommendations.append("Ensure all expected artifacts are generated")
        
        if metrics.grounding_score < 0.7:
            recommendations.append("Improve evidence collection for better grounding")
        
        if metrics.latency_score < 0.5:
            recommendations.append("Optimize execution for lower latency")
        
        if metrics.cost_efficiency_score < 0.5:
            recommendations.append("Review cost usage and consider optimization")
        
        return recommendations
    
    async def _call_llm_for_review(
        self,
        eval_result: EvaluationResult,
        task_id: str,
        tenant_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Call LLM for evaluation review"""
        try:
            prompt_data = self.prompt_loader.load_prompt("evaluation", "reviewer", "v1")
        except Exception:
            return {}, {"llm_used": False}
        
        # Build context summary
        context_summary = json.dumps(eval_result.to_dict(), indent=2, ensure_ascii=False)[:2000]
        
        user_prompt = prompt_data.get(
            "user_prompt_template",
            "Review evaluation: {context_summary}"
        ).format(context_summary=context_summary)
        
        result, meta = await self.llm_adapter.call(
            system_prompt=prompt_data.get("system_prompt", "You are a quality evaluator."),
            user_prompt=user_prompt,
            schema=prompt_data.get("json_schema", {}),
            meta={"prompt_version": prompt_data.get("version", "1.0")},
            task_id=task_id,
            tenant_id=tenant_id
        )
        
        return result, meta
    
    def _save_evaluation_artifact(
        self,
        task_id: str,
        eval_result: EvaluationResult,
        llm_output: Optional[Dict[str, Any]]
    ):
        """Save evaluation artifact"""
        # Save to task-specific directory
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        os.makedirs(artifact_dir, exist_ok=True)
        
        eval_data = eval_result.to_dict()
        if llm_output:
            eval_data["llm_insights"] = llm_output
        
        eval_path = os.path.join(artifact_dir, "evaluation.json")
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2, ensure_ascii=False)
        
        # Also save to global eval directory for regression detection
        global_eval_dir = "artifacts/eval"
        os.makedirs(global_eval_dir, exist_ok=True)
        
        global_eval_path = os.path.join(global_eval_dir, f"{task_id}.json")
        with open(global_eval_path, "w", encoding="utf-8") as f:
            json.dump({
                "run_id": task_id,
                "task_type": "general",  # Could be extracted from context
                "quality_score": eval_result.quality_score,
                "cost": 0.0,  # Could be extracted from context
                "latency": eval_result.latency_ms,
                "success": eval_result.passed,
                "timestamp": eval_result.evaluated_at
            }, f, indent=2)
    
    def get_governing_question(self) -> str:
        return "是否完成？是否达到成功标准？质量是否达标？"
