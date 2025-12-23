"""
Execution Engine: 执行引擎（多 Agent 协作版本 + 治理层）
目标：真实执行多 Agent 协作路径，并在关键检查点进行治理决策
流程：Orchestrator → Product → Data → Execution → Evaluation → Cost → COMPLETED
治理检查点：在每个关键阶段后插入治理检查
"""
from typing import Dict, Any, List, Optional
from runtime.state.state_manager import StateManager
from runtime.agents.product_agent import ProductAgent
from runtime.agents.data_agent import DataAgent
from runtime.agents.execution_agent import ExecutionAgent
from runtime.agents.evaluation_agent import EvaluationAgent
from runtime.agents.cost_agent import CostAgent
from runtime.governance.agent_report import AgentExecutionReport
from runtime.governance.governance_engine import GovernanceEngine, ExecutionMode
from runtime.execution_plan.plan_selector import PlanSelector
from runtime.execution_plan.plan_definition import ExecutionPlan, PlanNode
from runtime.tools.tool_dispatcher import ToolDispatcher
from runtime.platform.trace_store import TraceStore, TraceEvent
from runtime.decision_agents.intent_agent import IntentUnderstandingAgent
from runtime.decision_agents.query_transformation_agent import QueryTransformationAgent
from runtime.decision_agents.candidate_ranking_agent import CandidateRankingAgent
from runtime.decision_agents.dialogue_strategy_agent import DialogueStrategyAgent
from runtime.decision_agents.decision_context import DecisionContext
from runtime.platform.event_stream import EventStream
from runtime.learning.learning_controller import LearningController
from runtime.learning.l5_pipeline import maybe_train_and_rollout
from runtime.planning.llm_planner import get_llm_planner, TaskComplexity
from runtime.execution_graph.evolvable_dag import EvolvableDAG, DAGNode, MutationType
from learning.structural_learning import get_structural_learner, StructuralFeatureExtractor, StructuralRewardComputer, StructuralCreditAssigner
from learning.tenant_learning import get_tenant_learning_controller
from learning.unified_policy import TaskSuccessRewardComputer
from datetime import datetime
import uuid

class ExecutionEngine:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.agents = {
            "Product": ProductAgent(),
            "Data": DataAgent(),
            "Execution": ExecutionAgent(),
            "Evaluation": EvaluationAgent(),
            "Cost": CostAgent()
        }
        self.execution_trace: List[Dict[str, Any]] = []
        self.governance_engine = GovernanceEngine()
        self.plan_selector = PlanSelector()
        self.tool_dispatcher = ToolDispatcher()
        self.agent_reports: List[AgentExecutionReport] = []
        self.governance_decisions: List[Dict[str, Any]] = []
        self.current_plan: Optional[ExecutionPlan] = None
        self.plan_selection_history: List[Dict[str, Any]] = []
        self.tool_executions: List[Dict[str, Any]] = []
        self.decision_agents = {
            "intent": IntentUnderstandingAgent(),
            "query": QueryTransformationAgent(),
            "ranking": CandidateRankingAgent(),
            "strategy": DialogueStrategyAgent(),
        }
        self.decision_context: Optional[DecisionContext] = None
        
        # Phase 4: 平台层集成
        self.trace_store = TraceStore()
        self.event_stream = EventStream(self.trace_store)
        
        # Learning v1: 自动学习控制器（完全后台化，对用户无感）
        self.learning_controller = LearningController(
            trace_store=self.trace_store,
            policy_dir="artifacts/policies",
            min_runs=500,
            max_failure_rate=0.15,
            min_runs_between_training=1000
        )
        
        # Industrial v2: New components
        self.llm_planner = get_llm_planner()
        self.structural_learner = get_structural_learner()
        self.tenant_learning = get_tenant_learning_controller()
        self.reward_computer = TaskSuccessRewardComputer()
        self.structural_reward_computer = StructuralRewardComputer()
        self.credit_assigner = StructuralCreditAssigner()
        self.current_evolvable_dag: Optional[EvolvableDAG] = None
        
        self.event_counter = 0  # 用于生成 event_id
    
    async def initialize(self):
        """初始化执行引擎"""
        # 初始化 StateManager（确保持久化层可用）
        try:
            await self.state_manager.initialize()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize StateManager: {e}")

        # 验证 TraceStore 可用（目录可创建）
        try:
            # TraceStore constructor already ensures directories exist
            _ = self.trace_store
        except Exception as e:
            raise RuntimeError(f"TraceStore initialization failed: {e}")

        # 验证 EventStream 可用
        try:
            _ = self.event_stream
        except Exception as e:
            raise RuntimeError(f"EventStream initialization failed: {e}")

        # 验证 PlanRegistry / PlanSelector 至少包含默认计划
        try:
            plans = self.plan_selector.registry.list_plans()
            if not plans or len(plans) == 0:
                raise RuntimeError("No execution plans registered in PlanRegistry")
        except Exception as e:
            raise RuntimeError(f"PlanSelector/PlanRegistry validation failed: {e}")

        # 加载运行时配置（如果存在）
        try:
            import yaml, os
            cfg_path = os.environ.get("RUNTIME_CONFIG_PATH", "configs/runtime.yaml")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    self.runtime_config = cfg.get("runtime", {})
            else:
                # 退回到系统级配置
                sys_cfg_path = os.environ.get("SYSTEM_CONFIG_PATH", "configs/system.yaml")
                if os.path.exists(sys_cfg_path):
                    with open(sys_cfg_path, "r", encoding="utf-8") as f:
                        sys_cfg = yaml.safe_load(f) or {}
                        self.runtime_config = sys_cfg
                else:
                    self.runtime_config = {}
        except Exception:
            # 非致命：使用空配置
            self.runtime_config = {}

        # 初始化 observability/metrics hooks（若存在）
        try:
            from runtime.platform.metrics import MetricsRegistry
            self.metrics = MetricsRegistry.get_default()
        except Exception:
            self.metrics = None

        # Sanity: ensure required keys exist with safe defaults
        self.runtime_config.setdefault("budget", {}).setdefault("default_max_cost", 1000.0)
        self.runtime_config.setdefault("llm", {}).setdefault("mode", "mock")
        # 初始化完成
        return
    
    async def start_execution(self, task_id: str):
        """
        启动执行流程（多 Agent 协作）
        状态迁移：SPEC_READY → RUNNING → COMPLETED
        """
        # 状态已由 Orchestrator 设置为 SPEC_READY
        # 这里设置为 RUNNING
        await self.state_manager.update_task_state(
            task_id, 
            "RUNNING",
            reason="Execution engine started"
        )
        
        self.execution_trace = []
        self.agent_reports = []
        self.governance_decisions = []
        self.current_plan = None
        self.plan_selection_history = []
        self.tool_executions = []
        self.decision_context = None
        
        try:
            # 获取任务上下文
            context = await self.state_manager.get_task_context(task_id)
            spec = context.get("spec", {})
            user_input = context.get("user_input") or spec.get("audience") or ""
            
            decision_context = self._run_decision_layer(context, task_id)
            self.decision_context = decision_context
            context["decision_context"] = decision_context.to_dict()
            await self.state_manager.update_task_context(task_id, context)
            
            # Initial governance decision
            total_cost = 0.0
            budget_limit = float(
                self.runtime_config.get("budget", {}).get("default_max_cost", 1000.0)
            )
            llm_fallback_count = 0
            
            initial_gov_decision = self.governance_engine.make_decision(
                reports=[],
                total_cost=total_cost,
                budget_limit=budget_limit,
                llm_fallback_count=llm_fallback_count
            )
            
            # 1. Goal-driven Planning (P0-1 Upgrade)
            goal_text = context.get("query") or spec.get("goal") or user_input
            decomposition, planning_rationale = await self.llm_planner.plan(
                run_id=task_id,
                goal=goal_text,
                context=context
            )
            context["goal_decomposition"] = decomposition.to_dict()
            context["planning_rationale"] = planning_rationale.to_dict()
            
            # 2. Initialize Evolvable DAG (P0-2 Upgrade)
            self.current_evolvable_dag = EvolvableDAG(
                dag_id=f"dag_{task_id}",
                run_id=task_id
            )
            
            # Convert subgoals to DAG nodes
            for sg in decomposition.subgoals:
                node = DAGNode(
                    node_id=sg.subgoal_id,
                    agent_name=sg.assigned_agent,
                    description=sg.description,
                    dependencies=sg.dependencies,
                    cost_estimate=sg.estimated_cost,
                    latency_estimate_ms=sg.estimated_latency_ms,
                    risk_level=sg.risk_level
                )
                # Map to current agents
                if node.agent_name not in self.agents and node.agent_name.replace("Agent", "") in self.agents:
                    node.agent_name = node.agent_name.replace("Agent", "")
                
                self.current_evolvable_dag.add_node(node)
            
            # Reconstruct edges from dependencies
            for sg in decomposition.subgoals:
                for dep_id in sg.dependencies:
                    self.current_evolvable_dag.edges.add((dep_id, sg.subgoal_id))
            
            # Apply structural policy recommendation (with fallback)
            try:
                from learning.structural_learning import get_structural_learner

                structural_learner = get_structural_learner()
                recommended = structural_learner.recommend_structure(
                    task_type=goal.goal_type.value if hasattr(goal, "goal_type") else "general",
                    available_templates=list(self.current_evolvable_dag.nodes.keys()),
                    complexity=goal.goal_type.value if hasattr(goal, "goal_type") else "general",
                )
                if recommended and recommended.get("recommended_agents"):
                    # Reorder nodes to follow recommended agent sequence when possible
                    new_order = []
                    for agent_name in recommended["recommended_agents"]:
                        for n in self.current_evolvable_dag.nodes.values():
                            if n.agent_name == agent_name and n.node_id not in new_order:
                                new_order.append(n.node_id)
                    # Append remaining nodes
                    for n in self.current_evolvable_dag.nodes.values():
                        if n.node_id not in new_order:
                            new_order.append(n.node_id)
                    self.current_evolvable_dag.reorder_nodes(new_order, reason="structural_policy_applied")
                    context["structural_policy_applied"] = True
                    context["structural_policy_confidence"] = recommended.get("confidence", 0.0)
                else:
                    context["structural_policy_applied"] = False
            except Exception:
                context["structural_policy_applied"] = False

            # Initial signals for execution
            total_cost = 0.0
            budget_limit = float(
                self.runtime_config.get("budget", {}).get("default_max_cost", 1000.0)
            )
            
            # Get executable nodes from the dynamic DAG
            current_signals = {
                "budget_remaining": budget_limit,
                "risk_level": "low"
            }
            executable_nodes = self.current_evolvable_dag.get_executable_order(current_signals)
            
            # 记录计划选择（兼容旧版审计）
            self.current_plan = selected_plan = self.plan_selector.select_plan(
                governance_decision=initial_gov_decision,
                signals=current_signals
            )
            
            # 执行计划中的节点
            for node in executable_nodes:
                # 更新信号（用于条件评估）
                current_signals = {
                    "budget_remaining": budget_limit - total_cost,
                    "risk_level": node.risk_level,
                    "last_evaluation_failed": context.get("last_evaluation_failed", False),
                    "last_failure_type": context.get("last_failure_type", "")
                }
                
                # 检查节点条件（动态条件评估）
                if not node.can_execute(current_signals):
                    # 条件不满足，跳过节点
                    self.current_evolvable_dag.skip_node(node.node_id, "condition_not_met")
                    continue
                
                # 执行节点对应的 Agent
                node.status = "running"
                agent_name = node.agent_name
                if agent_name not in self.agents:
                    # Fallback to Execution if agent not found
                    agent_name = "Execution"
                
                agent_result = await self._execute_agent(agent_name, context, task_id)
                node.status = "completed" if agent_result.get("decision") not in ["terminate", "failed"] else "failed"
                
                agent_report = AgentExecutionReport.from_agent_result(agent_name, agent_result)
                self.agent_reports.append(agent_report)
                
                # Phase 4: 发送 Agent 执行事件
                self._emit_event(task_id, "agent_report", {
                    "agent_name": agent_name,
                    "node_id": node.node_id,
                    "decision": agent_result.get("decision"),
                    "status": "success" if node.status == "completed" else "error"
                })
                
                if agent_result.get("llm_result", {}).get("fallback_used"):
                    llm_fallback_count += 1
                
                # 更新成本
                # Recalculate total_cost from artifact cost_report.json (adapter writes estimated_cost)
                try:
                    import os, json
                    cost_path = os.path.join("artifacts", "rag_project", task_id, "cost_report.json")
                    if os.path.exists(cost_path):
                        with open(cost_path, "r", encoding="utf-8") as cf:
                            cost_entries = json.load(cf) or []
                            total_cost = sum(e.get("estimated_cost", 0.0) for e in cost_entries)
                    else:
                        # fallback to agent_report.cost_impact
                        total_cost += agent_report.cost_impact
                except Exception:
                    total_cost += agent_report.cost_impact
                
                # 治理检查点（在每个节点后）
                gov_decision = await self._governance_checkpoint(
                    task_id, context, total_cost, budget_limit, llm_fallback_count, f"after_{node.node_id}"
                )
                
                # Phase 4: 发送治理决策事件
                self._emit_event(task_id, "governance_decision", {
                    "checkpoint": f"after_{node.node_id}",
                    "execution_mode": gov_decision.get("execution_mode"),
                    "reasoning": gov_decision.get("reasoning", "")[:200]
                })
                
                # 如果治理决策是 PAUSED，停止执行
                if gov_decision["execution_mode"] == "paused":
                    await self.state_manager.update_task_state(
                        task_id, "FAILED",
                        reason=f"Governance paused: {gov_decision['reasoning']}"
                    )
                    await self._generate_artifacts(task_id, context, failed=True, error=gov_decision['reasoning'])
                    return
                
                # 检查是否需要切换计划（预算触发路径剪枝）
                if gov_decision["execution_mode"] in ["degraded", "minimal"]:
                    # 重新选择计划（基于新的治理决策）
                    new_signals = {
                        "budget_remaining": budget_limit - total_cost,
                        "risk_level": "medium" if gov_decision["execution_mode"] == "degraded" else "high"
                    }
                    new_gov_decision_obj = self.governance_engine.make_decision(
                        reports=self.agent_reports,
                        total_cost=total_cost,
                        budget_limit=budget_limit,
                        llm_fallback_count=llm_fallback_count
                    )
                    new_plan = self.plan_selector.select_plan(
                        governance_decision=new_gov_decision_obj,
                        signals=new_signals,
                        last_evaluation_feedback=last_evaluation_feedback if last_evaluation_feedback["failed"] else None
                    )
                    
                    # 如果计划改变，记录并切换
                    if new_plan.plan_id != selected_plan.plan_id:
                        selection_reasoning = self.plan_selector.get_selection_reasoning(
                            new_plan, new_gov_decision_obj, new_signals, last_evaluation_feedback if last_evaluation_feedback["failed"] else None
                        )
                        selection_reasoning["trigger"] = "budget_or_governance_change"
                        self.plan_selection_history.append(selection_reasoning)
                        selected_plan = new_plan
                        self.current_plan = new_plan
                        
                        # Phase 4: 发送计划切换事件
                        self._emit_event(task_id, "plan_switch", {
                            "from_plan_id": selected_plan.plan_id if selected_plan else None,
                            "to_plan_id": new_plan.plan_id,
                            "path_type": new_plan.path_type.value,
                            "trigger": "budget_or_governance_change"
                        })
                        
                        # 重新获取可执行节点
                        executable_nodes = selected_plan.get_executable_nodes(new_signals)
                
                # 更新上下文
                context = await self._update_context_from_result(task_id, agent_result)
                
                # Evaluation Agent 特殊处理：提取回流信号
                if node.agent_name == "Evaluation":
                    eval_result = agent_result.get("evaluation_result", {})
                    if eval_result:
                        # 更新上下文中的 Evaluation 反馈（用于下次执行回流）
                        context["last_evaluation_failed"] = not eval_result.get("passed", True)
                        context["last_failure_type"] = eval_result.get("failure_type")
                        context["last_blame_hint"] = eval_result.get("blame_hint")
                        await self.state_manager.update_task_context(task_id, context)
                
                # Cost Agent 检查（如果节点是 Cost）
                if node.agent_name == "Cost":
                    if agent_result["decision"] != "continue":
                        await self.state_manager.update_task_state(
                            task_id, "FAILED",
                            reason=f"Cost Agent terminated: {agent_result.get('reason')}"
                        )
                        await self._generate_artifacts(task_id, context, failed=True, error=agent_result.get('reason'))
                        return
                else:
                    # 非 Cost Agent 的决策检查
                    expected_decisions = {
                        "Product": "proceed",
                        "Data": "data_ready",
                        "Execution": "execution_complete",
                        "Evaluation": "passed"
                    }
                    if node.agent_name in expected_decisions:
                        if agent_result["decision"] != expected_decisions[node.agent_name]:
                            # Evaluation 失败不直接抛出异常，而是记录到上下文供回流使用
                            if node.agent_name == "Evaluation":
                                # Evaluation 失败已记录到上下文，继续执行
                                pass
                            else:
                                raise Exception(f"{node.agent_name} Agent failed: {agent_result.get('reason')}")
            
            # 执行完成，生成最终产物
            await self._generate_artifacts(task_id, context)
            
            # 执行成功，状态迁移到 COMPLETED
            await self.state_manager.update_task_state(
                task_id, 
                "COMPLETED",
                reason="All plan nodes executed successfully",
                progress={"currentAgent": "All", "currentStep": "completed"}
            )
            
            # Learning v1: 自动触发学习流程（完全后台化，对用户无感）
            self._trigger_learning_if_needed(task_id)
        except Exception as e:
            # 执行失败，状态迁移到 FAILED（包含 traceback 以便审计）
            import traceback as _tb
            err_trace = _tb.format_exc()
            await self.state_manager.update_task_state(
                task_id,
                "FAILED",
                str(e),
                progress=None,
                reason=f"Execution failed: {str(e)}\nTRACE:{err_trace}"
            )
            # 即使失败也生成产物（包含错误信息和治理决策）
            try:
                await self._generate_artifacts(task_id, await self.state_manager.get_task_context(task_id), failed=True, error=str(e))
            except:
                pass
            
            # Learning v1: 失败的 run 也参与学习（帮助优化 failure_rate）
            self._trigger_learning_if_needed(task_id)
    
    async def _execute_agent(self, agent_name: str, context: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """执行单个 Agent 并记录 trace（包含 LLM 信息）"""
        agent = self.agents[agent_name]
        
        # 记录执行开始
        trace_entry = {
            "agent": agent_name,
            "input": {
                "context_keys": list(context.keys()),
                "task_id": task_id
            },
            "output": {},
            "llm_info": None,
            "timestamp": None
        }
        
        try:
            result = await agent.execute(context, task_id)
            
            # 提取 LLM 信息（如果存在）
            llm_result = result.get("llm_result")
            if llm_result:
                trace_entry["llm_info"] = {
                    "llm_used": llm_result.get("llm_used", False),
                    "provider": llm_result.get("provider"),
                    "model_name": llm_result.get("model_name"),
                    "prompt_version": llm_result.get("prompt_version"),
                    "sampling_params": llm_result.get("sampling_params"),
                    "timeout_sec": llm_result.get("timeout_sec"),
                    "retries": llm_result.get("retries", 0),
                    "prompt_hash": llm_result.get("prompt_hash"),
                    "output_hash": llm_result.get("output_hash"),
                    "output_summary": llm_result.get("output_summary"),
                    "fallback_used": llm_result.get("fallback_used", False),
                    "failure_code": llm_result.get("failure_code"),
                    "error": llm_result.get("error")
                }
            
            trace_entry["output"] = {
                "decision": result.get("decision"),
                "reason": result.get("reason"),
                "summary": {k: v for k, v in result.items() if k not in ["state_update", "llm_result", "tool_executions"]}
            }
            trace_entry["status"] = "success"
            
            # 提取工具调用信息（如果存在）
            tool_executions = result.get("tool_executions", [])
            if tool_executions:
                trace_entry["tool_executions"] = tool_executions
                # 记录到全局工具执行列表
                self.tool_executions.extend(tool_executions)
            
            # 创建 Agent 报告（用于治理层）
            agent_report = AgentExecutionReport.from_agent_result(agent_name, result)
            # 注意：这里不直接添加到 self.agent_reports，由调用方管理
            
        except Exception as e:
            trace_entry["output"] = {"error": str(e)}
            trace_entry["status"] = "failed"
            raise
        
        from datetime import datetime
        trace_entry["timestamp"] = datetime.now().isoformat()
        self.execution_trace.append(trace_entry)
        
        return result
    
    async def _governance_checkpoint(
        self,
        task_id: str,
        context: Dict[str, Any],
        total_cost: float,
        budget_limit: float,
        llm_fallback_count: int,
        checkpoint_name: str
    ) -> Dict[str, Any]:
        """
        治理检查点：汇总 Agent 信号，检测冲突，执行治理规则
        
        不改变执行流程，只进行决策和建议
        """
        try:
            # 基于当前报告进行治理决策
            decision = self.governance_engine.make_decision(
                reports=self.agent_reports,
                total_cost=total_cost,
                budget_limit=budget_limit,
                llm_fallback_count=llm_fallback_count
            )
            
            # 记录治理决策
            decision_dict = decision.to_dict()
            decision_dict["checkpoint"] = checkpoint_name
            self.governance_decisions.append(decision_dict)
            
            # 如果决策是 PAUSED，返回决策信息（由调用方处理）
            # 如果决策是 DEGRADED 或 MINIMAL，记录但不阻止执行（当前实现）
            # 如果决策是 NORMAL，继续执行
            
            return decision_dict
        except Exception as e:
            # 治理层失败不应阻止系统完成
            # 返回默认 NORMAL 决策
            return {
                "execution_mode": "normal",
                "restrictions": [],
                "reasoning": f"Governance checkpoint failed (non-blocking): {str(e)}",
                "conflicts": [],
                "metrics": {},
                "checkpoint": checkpoint_name
            }
    
    async def _update_context_from_result(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """从 Agent 结果更新上下文"""
        if result.get("state_update"):
            current_context = await self.state_manager.get_task_context(task_id)
            updated_context = {**current_context, **result["state_update"]}
            await self.state_manager.update_task_context(task_id, updated_context)
            return updated_context
        return await self.state_manager.get_task_context(task_id)
    
    async def _generate_artifacts(self, task_id: str, context: Dict[str, Any], failed: bool = False, error: str = None):
        """生成交付产物"""
        import os
        import json
        from datetime import datetime
        
        artifact_dir = os.path.join("artifacts", "rag_project", task_id)
        os.makedirs(artifact_dir, exist_ok=True)
        
        # 获取状态迁移记录
        state_transitions = await self.state_manager.get_state_transitions(task_id)
        task_state = await self.state_manager.get_task_state(task_id)
        
        # 1. delivery_manifest.json
        manifest = {
            "task_id": task_id,
            "spec": context.get("spec", {}),
            "decision_context": self.decision_context.to_dict() if self.decision_context else {},
            "executed_agents": [entry["agent"] for entry in self.execution_trace],
            "agent_outputs": {
                entry["agent"]: {
                    "decision": entry["output"].get("decision"),
                    "reason": entry["output"].get("reason"),
                    "summary": entry["output"].get("summary", {})
                }
                for entry in self.execution_trace
            },
            "final_state": task_state.state.value if task_state else "UNKNOWN",
            "created_at": datetime.now().isoformat(),
            "failed": failed,
            "error": error
        }
        
        manifest_path = os.path.join(artifact_dir, "delivery_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        # 2. README.md
        readme_path = os.path.join(artifact_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# Delivery Artifact\n\n")
            f.write(f"**Task ID**: {task_id}\n\n")
            f.write(f"**Created at**: {manifest['created_at']}\n\n")
            f.write(f"**Status**: {'FAILED' if failed else 'COMPLETED'}\n\n")
            if failed and error:
                f.write(f"**Error**: {error}\n\n")
            f.write(f"## Executed Agents\n\n")
            for agent_name in manifest["executed_agents"]:
                f.write(f"- {agent_name}\n")
            f.write(f"\n## Note\n\n")
            f.write(f"This artifact was generated by **Agentic AI Delivery OS**.\n\n")
            f.write(f"This is an **engineering delivery artifact**, not a demo.\n")
        
        # 3. system_trace.json（增强：包含治理决策、ExecutionPlan、工具调用信息）
        trace_data = {
            "task_id": task_id,
            "decision_context": self.decision_context.to_dict() if self.decision_context else {},
            "state_transitions": state_transitions,
            "agent_executions": self.execution_trace,
            "agent_reports": [r.to_dict() for r in self.agent_reports],
            "governance_decisions": self.governance_decisions,
            "execution_plan": {
                "plan_id": self.current_plan.plan_id if self.current_plan else None,
                "plan_version": self.current_plan.plan_version if self.current_plan else None,
                "path_type": self.current_plan.path_type.value if self.current_plan else None,
                "plan_definition": self.current_plan.to_dict() if self.current_plan else None,
                "plan_selection_history": self.plan_selection_history,
                "executed_nodes": [
                    {
                        "node_id": entry["agent"],
                        "agent_name": entry["agent"],
                        "timestamp": entry.get("timestamp"),
                        "tool_executions": entry.get("tool_executions", [])
                    }
                    for entry in self.execution_trace
                ],
                "conditions_evidence": self._extract_conditions_evidence()
            },
            "tool_executions": self.tool_executions,
            "evaluation_feedback_flow": {
                "last_evaluation_failed": context.get("last_evaluation_failed", False),
                "last_failure_type": context.get("last_failure_type"),
                "last_blame_hint": context.get("last_blame_hint"),
                "used_in_plan_selection": any(
                    h.get("signals_used", {}).get("last_evaluation_failed", False)
                    for h in self.plan_selection_history
                )
            },
            "final_context": {
                k: v for k, v in context.items() 
                if k not in ["spec"]  # spec 已在 manifest 中
            },
            "generated_at": datetime.now().isoformat()
        }
        
        trace_path = os.path.join(artifact_dir, "system_trace.json")
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
    
    def _extract_conditions_evidence(self) -> Dict[str, Any]:
        """提取条件命中证据（用于审计）"""
        evidence = {}
        for report in self.agent_reports:
            agent_name = report.agent_name
            evidence[agent_name] = {
                "budget_remaining": report.signals.get("budget_remaining"),
                "risk_level": report.risk_level.value,
                "confidence": report.confidence,
                "llm_fallback_used": report.llm_fallback_used
            }
        return evidence

    def _run_decision_layer(self, context: Dict[str, Any], task_id: str) -> DecisionContext:
        spec = context.get("spec", {})
        user_input = context.get("user_input") or spec.get("audience") or ""
        history_summary = context.get("history_summary", "")
        intent_payload = {
            "user_input": user_input,
            "history_summary": history_summary,
            "delivery_spec": spec,
        }
        intent_result = self.decision_agents["intent"].evaluate(intent_payload)
        self._emit_event(task_id, "decision_intent", intent_result)

        query_payload = {
            "original_query": context.get("query") or user_input,
            "intent_result": intent_result,
            "retrieval_constraints": context.get("retrieval_constraints", {}),
        }
        query_result = self.decision_agents["query"].rewrite(query_payload)
        self._emit_event(task_id, "decision_query_rewrite", query_result)

        ranking_input = context.get("candidate_options") or []
        ranking_preferences = context.get("strategy_preferences", {})
        ranking_result = self.decision_agents["ranking"].rank(ranking_input, ranking_preferences)
        self._emit_event(task_id, "decision_candidate_ranking", ranking_result)

        strategy_payload = {
            "history_summary": history_summary,
            "recent_status": context.get("recent_status", "success"),
            "cost_pressure": context.get("cost_pressure", 0.0),
            "failure_count": context.get("failure_count", 0),
        }
        strategy_result = self.decision_agents["strategy"].evaluate(strategy_payload)
        self._emit_event(task_id, "decision_dialogue_strategy", strategy_result)

        return DecisionContext(
            intent=intent_result,
            query=query_result,
            ranking=ranking_result,
            strategy=strategy_result,
        )

    def _emit_event(self, task_id: str, event_type: str, payload: Dict[str, Any]):
        from datetime import datetime
        self.event_counter += 1
        event = TraceEvent(
            event_id=f"{task_id}-{self.event_counter}",
            task_id=task_id,
            ts=datetime.now().isoformat(),
            type=event_type,
            payload=payload,
        )
        self.event_stream.emit_event(task_id, event)
    
    def _trigger_learning_if_needed(self, task_id: str):
        """
        Industrial v2 Learning Closure:
        1. Finalize trace to store
        2. Compute structural rewards and credit assignment
        3. Update StructuralLearner
        4. Update TenantLearningController
        5. Trigger L5 rollout pipeline
        """
        try:
            # Step 1: Finalize trace
            self._finalize_trace_to_store(task_id)
            
            # Step 2: Get context and result
            import os, json
            trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
            if not os.path.exists(trace_path):
                return
            
            with open(trace_path, "r", encoding="utf-8") as f:
                trace_data = json.load(f)
            
            # Step 3: Compute Reward (P3 Upgrade)
            outcome = {
                "success": any(entry["status"] == "success" for entry in self.execution_trace if entry["agent"] == "Execution"),
                "quality_score": next((entry["output"].get("summary", {}).get("quality_score", 0.5) 
                                     for entry in self.execution_trace if entry["agent"] == "Evaluation"), 0.5),
                "cost": sum(r.cost_impact for r in self.agent_reports),
                "latency_ms": sum(entry.get("latency_ms", 0) for entry in self.execution_trace if "latency_ms" in entry)
            }
            
            # Create structural feature vector
            if self.current_evolvable_dag:
                nodes_list = [n.to_dict() for n in self.current_evolvable_dag.nodes.values()]
                edges_list = list(self.current_evolvable_dag.edges)
                structure_vector = StructuralFeatureExtractor.extract(nodes_list, edges_list)
                
                # Compute structural reward
                reward = self.structural_reward_computer.compute(
                    run_id=task_id,
                    dag_id=self.current_evolvable_dag.dag_id,
                    execution_result=outcome,
                    dag_features=structure_vector
                )
                
                # Assign credit
                node_results = {entry["agent"]: {"success": entry["status"] == "success", "quality": 0.5} 
                               for entry in self.execution_trace}
                credit_assignment = self.credit_assigner.assign(
                    run_id=task_id,
                    dag_nodes=nodes_list,
                    dag_edges=edges_list,
                    node_execution_results=node_results,
                    final_reward=reward.total_reward
                )
                
                # Update learner
                task_type = trace_data.get("decision_context", {}).get("intent", {}).get("category", "general")
                self.structural_learner.record_execution(
                    task_type=task_type,
                    structure_vector=structure_vector,
                    reward=reward,
                    credit_assignment=credit_assignment
                )
                
                # Step 4: Tenant-level Learning (P1-2 Upgrade)
                tenant_id = trace_data.get("final_context", {}).get("tenant_id", "default")
                self.tenant_learning.record_execution(
                    tenant_id=tenant_id,
                    task_type=task_type,
                    strategy_id=self.current_evolvable_dag.dag_id,
                    agents_used=[entry["agent"] for entry in self.execution_trace],
                    success=outcome["success"],
                    cost=outcome["cost"],
                    latency_ms=outcome["latency_ms"],
                    quality_score=outcome["quality_score"]
                )
            
            # Step 5: L5 Pipeline (Rollout)
            l5_summary = maybe_train_and_rollout(
                trace_store=self.trace_store,
                execution_engine=self
            )
            
        except Exception as e:
            # Learning failure should not block system completion
            print(f"Learning closure error: {e}")
            pass
    
    def _finalize_trace_to_store(self, task_id: str):
        """
        将当前 run 的完整 trace 同步到 TraceStore。
        ExecutionEngine 已在 artifacts/rag_project/{task_id}/system_trace.json 中写入 trace，
        这里需要：
        1. 读取 system_trace.json
        2. 构建 TraceSummary 并保存到 TraceStore
        3. 索引任务（供后续查询使用）
        """
        import os
        import json
        
        try:
            # 读取 system_trace.json
            trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
            if not os.path.exists(trace_path):
                return
            
            with open(trace_path, "r", encoding="utf-8") as f:
                trace_data = json.load(f)
            
            # 构建 summary 并保存
            summary = self.trace_store.build_summary_from_trace(task_id, trace_data)
            self.trace_store.save_summary(summary)
            
            # 索引任务
            self.trace_store.index_trace(task_id, trace_data)
        
        except Exception:
            # 如果同步失败，不影响主流程
            pass
