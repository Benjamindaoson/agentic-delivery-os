"""
L5 Integrated Engine - Complete L5 closed-loop execution
Integrates all L5 components into a unified execution engine
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime

# L5 Components
from planner.goal_interpreter import get_interpreter
from planner.planner_agent import get_planner
from memory.agent_memory import AgentMemory
from memory.pattern_extractor import get_pattern_extractor
from generation.multi_candidate_generator import get_generator
from generation.generation_reranker import get_reranker
from evaluation.quality_scorer import get_scorer
from evaluation.benchmark_runner import get_benchmark_runner
from learning.feedback_collector import get_feedback_collector
from learning.policy_updater import get_policy_updater
from learning.strategy_store import get_strategy_store
from learning.bandit_selector import get_bandit_selector


class L5IntegratedEngine:
    """
    Complete L5 Execution Engine with Learning Closed-Loop
    Goal → Plan → Execute → Evaluate → Learn → Update Policy
    """
    
    def __init__(self):
        # Core components
        self.goal_interpreter = get_interpreter()
        self.planner = get_planner()
        self.generator = get_generator()
        self.reranker = get_reranker()
        self.scorer = get_scorer()
        self.feedback_collector = get_feedback_collector()
        self.policy_updater = get_policy_updater()
        self.strategy_store = get_strategy_store()
        self.pattern_extractor = get_pattern_extractor()
        
        # Agent memories
        self.agent_memories = {}
        
        # Bandit selectors
        self.planner_bandit = get_bandit_selector("planner", "ucb1")
        self.tool_bandit = get_bandit_selector("tool", "epsilon_greedy")
        
        # Initialize strategies
        self._initialize_strategies()
        
        # Statistics
        self.total_runs = 0
        self.policy_updates_triggered = 0
    
    def _initialize_strategies(self):
        """Initialize default strategies if not exists"""
        # Register bandit arms for planner strategies
        planner_strategies = ["sequential", "parallel", "hierarchical"]
        for strategy in planner_strategies:
            self.planner_bandit.register_arm(strategy)
        
        # Register tool strategies
        tool_strategies = ["retriever", "llm_generator", "summarizer"]
        for tool in tool_strategies:
            self.tool_bandit.register_arm(tool)
    
    def execute_with_learning(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute full L5 cycle: Goal → Plan → Execute → Evaluate → Learn
        Args:
            query: User query
            context: Optional execution context
        Returns:
            Complete execution result with learning metrics
        """
        run_id = f"l5_run_{uuid.uuid4().hex[:8]}"
        self.total_runs += 1
        
        execution_log = {
            "run_id": run_id,
            "query": query,
            "started_at": datetime.now().isoformat(),
            "stages": {}
        }
        
        try:
            # 1. GOAL INTERPRETATION
            print(f"[L5] Stage 1/7: Goal Interpretation")
            goal = self.goal_interpreter.interpret(query, context)
            execution_log["stages"]["goal"] = {
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type,
                "complexity": goal.estimated_complexity,
                "risk_level": goal.risk_level
            }
            
            # 2. INTELLIGENT PLANNING (with Bandit)
            print(f"[L5] Stage 2/7: Intelligent Planning")
            selected_strategy = self.planner_bandit.select_arm()
            execution_log["stages"]["strategy_selection"] = {
                "selected": selected_strategy,
                "algorithm": "ucb1"
            }
            
            plan = self.planner.create_plan(goal)
            execution_log["stages"]["plan"] = {
                "plan_id": plan.plan_id,
                "num_nodes": len(plan.nodes),
                "estimated_cost": plan.total_estimated_cost,
                "estimated_latency": plan.total_estimated_latency_ms
            }
            
            # 3. MULTI-CANDIDATE GENERATION
            print(f"[L5] Stage 3/7: Multi-Candidate Generation")
            gen_context = {"query": query, "documents": [{"content": f"Mock doc for {query}"}]}
            candidates_result = self.generator.generate_candidates(
                query=query,
                context=gen_context,
                num_candidates=3
            )
            execution_log["stages"]["generation"] = {
                "num_candidates": len(candidates_result.candidates),
                "total_cost": candidates_result.total_cost
            }
            
            # 4. RERANKING
            print(f"[L5] Stage 4/7: Evidence-Aware Reranking")
            rerank_result = self.reranker.rerank(
                candidates_result.candidates,
                gen_context
            )
            chosen_output = rerank_result.chosen_candidate.content
            execution_log["stages"]["reranking"] = {
                "chosen_rank": rerank_result.chosen_candidate.rank,
                "chosen_score": rerank_result.chosen_candidate.score.total_score
            }
            
            # 5. QUALITY EVALUATION
            print(f"[L5] Stage 5/7: Quality Assessment")
            quality_score = self.scorer.score(
                run_id=run_id,
                output=chosen_output,
                query=query,
                evidence=[{"content": "mock evidence"}]
            )
            execution_log["stages"]["evaluation"] = {
                "overall_score": quality_score.overall_score,
                "groundedness": quality_score.groundedness_score,
                "correctness": quality_score.correctness_score,
                "consistency": quality_score.consistency_score
            }
            
            # 6. FEEDBACK COLLECTION
            print(f"[L5] Stage 6/7: Feedback Collection")
            success = quality_score.overall_score >= 0.7
            self.feedback_collector.collect_auto_eval_feedback(
                run_id=run_id,
                quality_score=quality_score.overall_score,
                cost=candidates_result.total_cost,
                latency_ms=candidates_result.total_latency_ms,
                passed=success
            )
            
            # Update bandit with strategy reward
            strategy_reward = quality_score.overall_score
            self.planner_bandit.update_reward(selected_strategy, strategy_reward)
            
            execution_log["stages"]["feedback"] = {
                "collected": True,
                "strategy_reward": strategy_reward
            }
            
            # 7. POLICY UPDATE (if threshold met)
            print(f"[L5] Stage 7/7: Policy Update Check")
            recent_feedback = self.feedback_collector.get_recent_feedback(limit=50)
            
            if len(recent_feedback) >= 20:  # Threshold met
                current_policies = {
                    "planner_version": "1.0",
                    "tool_version": "1.0",
                    "agent_version": "1.0",
                    "generation_version": "1.0"
                }
                
                update_result = self.policy_updater.analyze_and_update(
                    recent_feedback,
                    current_policies
                )
                
                if update_result.success:
                    self.policy_updates_triggered += 1
                    print(f"  ✅ Policy Update Triggered! ({len(update_result.updates_applied)} updates)")
                    
                    # Save updated policies to strategy store
                    for update in update_result.updates_applied:
                        version = self.strategy_store.save_version(
                            policy_type=update.policy_type,
                            config=update.changes,
                            notes=f"Auto-update from feedback analysis"
                        )
                        self.strategy_store.activate_version(version.version_id)
                
                execution_log["stages"]["policy_update"] = {
                    "triggered": update_result.success,
                    "updates_applied": len(update_result.updates_applied),
                    "message": update_result.message
                }
            else:
                execution_log["stages"]["policy_update"] = {
                    "triggered": False,
                    "reason": f"Need {20 - len(recent_feedback)} more feedback items"
                }
            
            # 8. UPDATE AGENT MEMORY
            agent_id = "l5_agent"
            if agent_id not in self.agent_memories:
                self.agent_memories[agent_id] = AgentMemory(agent_id)
            
            self.agent_memories[agent_id].record_run(
                goal_type=goal.goal_type,
                tools_used=["retriever", "generator", "reranker"],
                success=success,
                quality_score=quality_score.overall_score,
                cost=candidates_result.total_cost,
                latency_ms=candidates_result.total_latency_ms
            )
            
            # Final result
            execution_log["completed_at"] = datetime.now().isoformat()
            execution_log["success"] = success
            execution_log["final_output"] = chosen_output
            execution_log["quality_score"] = quality_score.overall_score
            
            return execution_log
            
        except Exception as e:
            execution_log["error"] = str(e)
            execution_log["completed_at"] = datetime.now().isoformat()
            execution_log["success"] = False
            return execution_log
    
    def extract_and_learn_patterns(self):
        """Extract patterns from recent runs"""
        print("[L5] Extracting patterns from recent runs...")
        patterns = self.pattern_extractor.extract_from_recent_runs(window_days=7, min_runs=3)
        print(f"  ✅ Extracted {len(patterns)} patterns")
        return patterns
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "total_runs": self.total_runs,
            "policy_updates_triggered": self.policy_updates_triggered,
            "planner_bandit_stats": self.planner_bandit.get_statistics(),
            "tool_bandit_stats": self.tool_bandit.get_statistics(),
            "active_policies": {
                "planner": self.strategy_store.get_active_version("planner"),
                "tool_selection": self.strategy_store.get_active_version("tool_selection"),
                "agent_routing": self.strategy_store.get_active_version("agent_routing")
            },
            "agent_memories": {
                agent_id: memory.get_summary()
                for agent_id, memory in self.agent_memories.items()
            }
        }


# Singleton instance
_l5_engine = None

def get_l5_engine() -> L5IntegratedEngine:
    """Get singleton L5 engine instance"""
    global _l5_engine
    if _l5_engine is None:
        _l5_engine = L5IntegratedEngine()
    return _l5_engine



