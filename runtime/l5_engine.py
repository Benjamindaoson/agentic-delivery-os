import uuid
from datetime import datetime
from typing import Dict, Any, List

from runtime.session.manager import SessionManager
from runtime.ingress.classifier import TaskTypeClassifier
from runtime.planning.l5_planner import L5Planner
from runtime.agents.l5_agents import AgentManager
from runtime.tooling.l5_tooling import ToolManager
from runtime.memory.l5_memory import LongTermMemory, GlobalState
from runtime.eval.l5_eval import BenchmarkSuite, EvalResult
from runtime.learning.l5_learning import LearningController
from runtime.governance.l5_governance import GovernanceController

class L5Engine:
    def __init__(self):
        self.session_mgr = SessionManager()
        self.classifier = TaskTypeClassifier()
        self.planner = L5Planner()
        self.agent_mgr = AgentManager()
        self.tool_mgr = ToolManager()
        self.memory = LongTermMemory()
        self.global_state = GlobalState()
        self.benchmark = BenchmarkSuite()
        self.learning = LearningController()
        self.governance = GovernanceController()

    def execute_run(self, query: str, session_id: str = None, user_id: str = "default_user") -> Dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        session = self.session_mgr.get_or_create_session(session_id, user_id)
        self.session_mgr.add_run_to_session(session.session_id, run_id)

        # 1. Ingress & Classification
        classification = self.classifier.classify(run_id, query)

        # 2. Planning (Full causal chain)
        plan_chain = self.planner.plan_task(run_id, query, classification)

        # 3. Governance check
        if self.governance.check_injection(query):
            return {"run_id": run_id, "success": False, "reason": "Security violation"}

        # 4. Simulated Execution (Agent & Tool interaction)
        # In a real system, the planner output would drive this loop.
        tools_used = ["retriever", "summarizer"]
        success = True
        latency = 1200.0
        cost = 0.04
        
        # Record Tool Usage
        for tool in tools_used:
            self.tool_mgr.record_usage(tool, success, latency / len(tools_used), cost / len(tools_used))

        # Record Agent Usage
        self.agent_mgr.update_performance("data_agent", success, latency, cost, classification.task_type)

        # 5. Outcome & Eval
        eval_res = EvalResult(
            run_id=run_id,
            task_type=classification.task_type,
            quality_score=0.92,
            cost=cost,
            latency=latency,
            success=success
        )
        self.benchmark.record_eval(eval_res)

        # 6. Memory Storage
        self.memory.store(query, {"output": "Simulated result"}, classification.task_type, "success", run_id)
        self.global_state.update_stats(cost, tools_used)

        # 7. Learning (Auto-promotion)
        if eval_res.quality_score > 0.9:
            self.learning.promote_policy("data_agent", "High quality performance", {"quality_gain": 0.05})

        return {
            "run_id": run_id,
            "session_id": session.session_id,
            "classification": classification,
            "plan": plan_chain,
            "eval": eval_res
        }

if __name__ == "__main__":
    engine = L5Engine()
    result = engine.execute_run("What is the ROI of Agentic OS L5?")
    print(f"Run {result['run_id']} completed. Quality: {result['eval'].quality_score}")



