"""
Exploration Policy Engine (L5.5)

Decides when to explore, manages budgets, generates candidates, and links to shadow/replay.
Artifacts:
- artifacts/exploration/decisions/{run_id}.json
- artifacts/exploration/rewards/{run_id}.json
- artifacts/exploration/budget_state.json (via FailureBudget)
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from runtime.artifacts.artifact_schema import compute_inputs_hash, DEFAULT_SCHEMA_VERSION
from runtime.exploration.failure_budget import FailureBudget
from runtime.exploration.strategy_genome import StrategyGenome
from runtime.exploration.candidate_generator import CandidateGenerator
from runtime.policy.policy_registry import PolicyRegistry
from runtime.policy.policy_packager import PolicyPackager
from runtime.eval.golden_replay_suite import GoldenReplaySuite
from runtime.shadow.shadow_executor import ShadowExecutor
from runtime.eval.policy_regression_runner import PolicyRegressionRunner
from learning.semantic_task_success import compute_semantic_reward
from learning.structural_learning import (
    StructuralRewardComputer,
    get_structural_learner,
    StructuralFeatureExtractor,
    StructuralCreditAssigner,
)


class ExplorationEngine:
    def __init__(
        self,
        artifacts_dir: str = "artifacts",
        window_runs: int = 200,
        max_failures: int = 10,
        max_cost_usd: float = 5.0,
        max_latency_ms: float = 20000.0,
        exploration_enabled: bool = True,
        max_parallel_candidates: int = 2,
    ):
        self.artifacts_dir = artifacts_dir
        self.decisions_dir = os.path.join(artifacts_dir, "exploration", "decisions")
        self.rewards_dir = os.path.join(artifacts_dir, "exploration", "rewards")
        os.makedirs(self.decisions_dir, exist_ok=True)
        os.makedirs(self.rewards_dir, exist_ok=True)
        self.budget = FailureBudget(
            artifacts_dir=artifacts_dir,
            window_runs=window_runs,
            max_failures=max_failures,
            max_cost_usd=max_cost_usd,
            max_latency_ms=max_latency_ms,
        )
        self.registry = PolicyRegistry(artifacts_dir=artifacts_dir)
        self.packager = PolicyPackager(artifacts_dir=artifacts_dir)
        self.generator = CandidateGenerator(artifacts_dir=artifacts_dir)
        self.golden_suite = GoldenReplaySuite(artifacts_dir=artifacts_dir)
        self.shadow_executor = ShadowExecutor(artifacts_dir=artifacts_dir)
        self.regression_runner = PolicyRegressionRunner(artifacts_dir=artifacts_dir)
        self.exploration_enabled = exploration_enabled
        self.max_parallel_candidates = max_parallel_candidates

    async def maybe_explore(
        self,
        run_id: str,
        run_signals: Dict[str, Any],
        attribution: Optional[Dict[str, Any]] = None,
        policy_kpis: Optional[Dict[str, Any]] = None,
        feedback_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Main exploration entry."""
        decision = self._decide(run_id, run_signals, attribution, policy_kpis, feedback_events)
        self._persist_decision(run_id, decision)

        if not decision["decision"]["explore"]:
            return decision

        # Respect budget
        spend_ok = self.budget.can_spend(failures=1, cost_usd=0.1, latency_ms=500)
        if not spend_ok:
            decision["decision"]["explore"] = False
            decision["budgets"]["remaining"] = self.budget.state["remaining"]
            decision["guards"]["hard_stop"] = True
            return decision

        # Generate candidates
        base_genome = StrategyGenome(
            schema_version=DEFAULT_SCHEMA_VERSION,
            retrieval_policy_id=run_signals.get("retrieval_policy_id", "basic_v1"),
            prompt_template_id=run_signals.get("generation_template_id", "default_prompt"),
            tool_chain_id=run_signals.get("pattern_hash", "tool_chain_default"),
            planner_mode=run_signals.get("planner_choice", "normal"),
            params={"top_k": 10, "tool_timeout": 1000},
        )
        candidates = self.generator.generate_candidates(
            base_genome,
            available_retrieval=["basic_v1", "semantic_rerank_v1", "hybrid_v1"],
            available_prompts=["rag_answer:v1", "product_spec_interpreter", "test_template:v1"],
            available_tools=["tool_chain_a", "tool_chain_b"],
            count=min(decision["decision"]["candidate_count"], self.max_parallel_candidates),
        )
        for cand in candidates:
            self.registry.add_candidate(cand["candidate_id"])

        # Run shadow + regression for first candidate (simplified)
        if candidates:
            cid = candidates[0]["candidate_id"]
            await self._shadow_and_replay(run_id, cid, run_signals)
        return decision

    def _decide(
        self,
        run_id: str,
        run_signals: Dict[str, Any],
        attribution: Optional[Dict[str, Any]],
        policy_kpis: Optional[Dict[str, Any]],
        feedback_events: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        explore = False
        reason_codes = []
        uncertainty_score = 0.0
        novelty_score = 0.0
        regression_risk = 0.0

        # Rule 1: uncertainty high if success fluctuates
        success_rate = policy_kpis.get("success_rate", 1.0) if policy_kpis else 1.0
        if success_rate < 0.8:
            explore = True
            reason_codes.append("low_success_rate")
            uncertainty_score += (0.8 - success_rate)

        # Rule 2: new pattern with failures
        if run_signals.get("pattern_is_new") and not run_signals.get("run_success"):
            explore = True
            reason_codes.append("new_pattern_failure")
            novelty_score += 0.5

        # Rule 3: attribution points to specific layer
        target_space = ["retrieval", "prompt", "tool_combo"]
        if attribution:
            primary = attribution.get("primary_cause")
            if primary == "RETRIEVAL_MISS":
                target_space = ["retrieval"]
            elif primary == "PROMPT_MISMATCH":
                target_space = ["prompt"]
            elif primary == "TOOL_TIMEOUT":
                target_space = ["tool_combo"]

        # Budget guard
        guards = {"must_shadow": True, "must_replay": True, "max_parallel_candidates": self.max_parallel_candidates}
        budgets = {
            "remaining": self.budget.state["remaining"],
            "spent": self.budget.state["spent"],
        }

        decision_payload = {
            "schema_version": DEFAULT_SCHEMA_VERSION,
            "run_id": run_id,
            "decision": {
                "explore": self.exploration_enabled and explore and not self.budget.state["guards"]["hard_stop"],
                "mode": "shadow_only",
                "target_space": target_space,
                "candidate_count": 1,
            },
            "trigger": {
                "reason_codes": reason_codes,
                "uncertainty_score": round(uncertainty_score, 3),
                "novelty_score": round(novelty_score, 3),
                "regression_risk": round(regression_risk, 3),
            },
            "budgets": budgets,
            "constraints": guards,
            "links": {},
            "timestamp": datetime.now().isoformat(),
        }
        decision_payload["inputs_hash"] = compute_inputs_hash(run_signals)
        decision_payload["guards"] = self.budget.state["guards"]
        return decision_payload

    def _persist_decision(self, run_id: str, decision: Dict[str, Any]) -> None:
        os.makedirs(self.decisions_dir, exist_ok=True)
        path = os.path.join(self.decisions_dir, f"{run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decision, f, indent=2, ensure_ascii=False)

    async def _shadow_and_replay(self, run_id: str, candidate_id: str, run_signals: Dict[str, Any]) -> None:
        # dummy runner simulating execution
        async def runner(payload):
            return {
                "decision": "candidate",
                "success": True,
                "cost": 0.05,
                "latency_ms": 150,
                "evidence_usage_rate": run_signals.get("evidence_usage_rate", 0.5),
            }

        # shadow execution diff (real shadow executor)
        diff = await self.shadow_executor.run_shadow(
            run_id=f"{run_id}_{candidate_id}_shadow",
            input_payload=run_signals,
            active_runner=runner,
            candidate_runner=runner,
        )

        # golden replay (real suite)
        suite = self.golden_suite.build_suite(
            fixed_golden=[{"input": "golden"}],
            recent_failures=[run_signals],
            new_patterns=[run_signals] if run_signals.get("pattern_is_new") else [],
            limit=5,
        )
        replay_report = await self.golden_suite.run_suite(candidate_id, suite, runner)

        # regression gate
        verdict = await self.regression_runner.run(
            candidate_policy_id=candidate_id,
            historical_runs=suite,
            golden_results=[{"expected_success": True, "expected_cost": 0.05} for _ in suite],
            candidate_runner=runner,
        )
        if not verdict.pass_regression:
            self.registry.mark_rejected(candidate_id)
        else:
            self.registry.add_shadow(candidate_id)

        # reward: semantic + structural
        semantic_reward, detail = compute_semantic_reward(
            quality_score=run_signals.get("quality_score", 0.6),
            grounding_score=run_signals.get("grounding_score", 0.6),
            cost_efficiency=run_signals.get("cost_efficiency", 0.6),
            user_intent_match=run_signals.get("user_intent_match", 0.6),
            task_id=run_id,
        )

        structural_reward_val = 0.0
        try:
            structural_learner = get_structural_learner()
            nodes = run_signals.get("dag_nodes", [])
            edges = run_signals.get("dag_edges", [])
            if nodes and edges:
                vector = StructuralFeatureExtractor.extract(nodes, edges)
                structural_computer = StructuralRewardComputer()
                structural_reward = structural_computer.compute(
                    run_id=run_id,
                    dag_id=nodes[0].get("dag_id", "unknown"),
                    execution_result={
                        "success": run_signals.get("run_success", True),
                        "quality_score": run_signals.get("quality_score", 0.6),
                        "total_cost": run_signals.get("total_cost", 0.0),
                        "total_latency_ms": run_signals.get("latency_ms", 0),
                    },
                    dag_features=vector,
                )
                structural_reward_val = structural_reward.total_reward

                # Credit assignment
                credit_assigner = StructuralCreditAssigner()
                node_results = run_signals.get("node_execution_results", {})
                credit_assignment = credit_assigner.assign(
                    run_id=run_id,
                    dag_nodes=nodes,
                    dag_edges=edges,
                    node_execution_results=node_results,
                    final_reward=structural_reward_val,
                )

                structural_learner.record_execution(
                    task_type=run_signals.get("goal_type", "general"),
                    structure_vector=vector,
                    reward=structural_reward,
                    credit_assignment=credit_assignment,
                )
        except Exception:
            structural_reward_val = 0.0

        total_reward = semantic_reward + structural_reward_val
        reward_payload = {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "semantic_reward": semantic_reward,
            "structural_reward": structural_reward_val,
            "total_reward": total_reward,
            "detail": detail,
        }
        reward_path = os.path.join(self.rewards_dir, f"{run_id}.json")
        with open(reward_path, "w", encoding="utf-8") as f:
            json.dump(reward_payload, f, indent=2, ensure_ascii=False)

