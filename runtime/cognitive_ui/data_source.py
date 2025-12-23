"""
ArtifactDataSource: Read-only abstraction layer for artifacts
Only reads local artifacts, no ExecutionEngine/LLM calls
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class ArtifactDataSource:
    """
    Read-only data source for Cognitive Workbench UI
    
    Features:
    - List all tasks from artifacts
    - Load task summaries, traces, costs, governance
    - Diff two tasks
    - Compatible with multiple artifact naming patterns
    """
    
    def __init__(self, artifacts_root: str = "artifacts"):
        self.artifacts_root = artifacts_root
        self.rag_project_dir = os.path.join(artifacts_root, "rag_project")
        self.trace_store_dir = os.path.join(artifacts_root, "trace_store")
        self.tenants_dir = os.path.join(artifacts_root, "tenants")
        self.execution_dir = os.path.join(artifacts_root, "execution")
    
    def list_tasks(self) -> List[str]:
        """
        List all task IDs from artifacts
        
        Searches multiple locations:
        - artifacts/rag_project/{task_id}/
        - artifacts/trace_store/summaries/{task_id}.json
        """
        task_ids = set()
        
        # From rag_project
        if os.path.exists(self.rag_project_dir):
            try:
                for item in os.listdir(self.rag_project_dir):
                    item_path = os.path.join(self.rag_project_dir, item)
                    if os.path.isdir(item_path):
                        task_ids.add(item)
            except Exception:
                pass
        
        # From trace_store summaries
        summaries_dir = os.path.join(self.trace_store_dir, "summaries")
        if os.path.exists(summaries_dir):
            try:
                for filename in os.listdir(summaries_dir):
                    if filename.endswith(".json"):
                        task_id = filename.replace(".json", "")
                        task_ids.add(task_id)
            except Exception:
                pass
        
        return sorted(list(task_ids))
    
    def load_task_summary(self, task_id: str) -> Dict[str, Any]:
        """
        Load task summary (basic info)
        
        Tries multiple paths:
        - artifacts/rag_project/{task_id}/delivery_manifest.json
        - artifacts/trace_store/summaries/{task_id}.json
        """
        summary = {
            "task_id": task_id,
            "status": "unknown",
            "created_at": None,
            "spec": {},
            "agents_executed": [],
            "error": None
        }
        
        # Try delivery_manifest.json
        manifest_path = os.path.join(self.rag_project_dir, task_id, "delivery_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    summary.update({
                        "status": "failed" if manifest.get("failed") else "completed",
                        "created_at": manifest.get("created_at"),
                        "spec": manifest.get("spec", {}),
                        "agents_executed": manifest.get("executed_agents", []),
                        "error": manifest.get("error")
                    })
            except Exception:
                pass
        
        # Try trace_store summary
        trace_summary_path = os.path.join(self.trace_store_dir, "summaries", f"{task_id}.json")
        if os.path.exists(trace_summary_path):
            try:
                with open(trace_summary_path, "r", encoding="utf-8") as f:
                    trace_summary = json.load(f)
                    summary.update({
                        "status": trace_summary.get("state", "unknown"),
                        "created_at": trace_summary.get("created_at"),
                        "result_summary": trace_summary.get("result_summary", {})
                    })
            except Exception:
                pass
        
        return summary
    
    def load_timeline_events(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Load timeline events (simplified version from existing traces)
        
        Assembles from:
        - artifacts/rag_project/{task_id}/system_trace.json
        - artifacts/execution/tool_traces/{task_id}.jsonl
        - artifacts/trace_store/events/{task_id}.jsonl
        """
        events = []
        
        # From system_trace.json (agent executions)
        system_trace_path = os.path.join(self.rag_project_dir, task_id, "system_trace.json")
        if os.path.exists(system_trace_path):
            try:
                with open(system_trace_path, "r", encoding="utf-8") as f:
                    trace = json.load(f)
                    
                    # Agent executions
                    for agent_exec in trace.get("agent_executions", []):
                        events.append({
                            "timestamp": agent_exec.get("timestamp"),
                            "type": "agent_execution",
                            "agent": agent_exec.get("agent"),
                            "status": agent_exec.get("status", "success"),
                            "details": {
                                "decision": agent_exec.get("output", {}).get("decision"),
                                "llm_used": agent_exec.get("llm_info", {}).get("llm_used", False)
                            }
                        })
                    
                    # Governance decisions
                    for gov_decision in trace.get("governance_decisions", []):
                        events.append({
                            "timestamp": gov_decision.get("timestamp"),
                            "type": "governance_decision",
                            "checkpoint": gov_decision.get("checkpoint"),
                            "execution_mode": gov_decision.get("execution_mode"),
                            "details": {
                                "reasoning": gov_decision.get("reasoning", "")[:200]
                            }
                        })
            except Exception:
                pass
        
        # From tool traces
        tool_trace_path = os.path.join(self.artifacts_root, "execution", "tool_traces", f"{task_id}.jsonl")
        if os.path.exists(tool_trace_path):
            try:
                with open(tool_trace_path, "r", encoding="utf-8") as f:
                    for line in f:
                        tool_trace = json.loads(line.strip())
                        events.append({
                            "timestamp": tool_trace.get("timestamp"),
                            "type": "tool_execution",
                            "tool_name": tool_trace.get("tool_name"),
                            "status": "success" if tool_trace.get("success") else "failed",
                            "details": {
                                "execution_time_ms": tool_trace.get("execution_time_ms"),
                                "error": tool_trace.get("error")
                            }
                        })
            except Exception:
                pass
        
        # From trace_store events
        events_path = os.path.join(self.trace_store_dir, "events", f"{task_id}.jsonl")
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    for line in f:
                        event = json.loads(line.strip())
                        events.append({
                            "timestamp": event.get("ts"),
                            "type": event.get("type"),
                            "event_id": event.get("event_id"),
                            "details": event.get("payload", {})
                        })
            except Exception:
                pass
        
        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp") or "")
        
        return events
    
    def load_cost(self, task_id: str) -> Dict[str, Any]:
        """
        Load cost information
        
        Tries:
        - artifacts/rag_project/{task_id}/cost_report.json
        - artifacts/rag_project/{task_id}/cost_decision.json
        """
        cost_info = {
            "total_cost": 0.0,
            "cost_breakdown": {},
            "cost_decision": None
        }
        
        # From cost_report.json
        cost_report_path = os.path.join(self.rag_project_dir, task_id, "cost_report.json")
        if os.path.exists(cost_report_path):
            try:
                with open(cost_report_path, "r", encoding="utf-8") as f:
                    cost_entries = json.load(f)
                    if isinstance(cost_entries, list):
                        total = sum(e.get("estimated_cost", 0.0) for e in cost_entries)
                        cost_info["total_cost"] = total
                        
                        # Breakdown by provider
                        breakdown = {}
                        for entry in cost_entries:
                            provider = entry.get("provider", "unknown")
                            cost = entry.get("estimated_cost", 0.0)
                            breakdown[provider] = breakdown.get(provider, 0.0) + cost
                        cost_info["cost_breakdown"] = breakdown
            except Exception:
                pass
        
        # From cost_decision.json
        cost_decision_path = os.path.join(self.rag_project_dir, task_id, "cost_decision.json")
        if os.path.exists(cost_decision_path):
            try:
                with open(cost_decision_path, "r", encoding="utf-8") as f:
                    cost_info["cost_decision"] = json.load(f)
            except Exception:
                pass
        
        return cost_info
    
    def load_governance(self, task_id: str) -> Dict[str, Any]:
        """
        Load governance information
        
        Tries:
        - artifacts/rag_project/{task_id}/system_trace.json (governance_decisions)
        - artifacts/governance_logs/{task_id}.json
        """
        governance_info = {
            "decisions": [],
            "restrictions": [],
            "degraded": False
        }
        
        # From system_trace.json
        system_trace_path = os.path.join(self.rag_project_dir, task_id, "system_trace.json")
        if os.path.exists(system_trace_path):
            try:
                with open(system_trace_path, "r", encoding="utf-8") as f:
                    trace = json.load(f)
                    governance_info["decisions"] = trace.get("governance_decisions", [])
                    
                    # Check if any degraded mode
                    for decision in governance_info["decisions"]:
                        if decision.get("execution_mode") in ["degraded", "minimal"]:
                            governance_info["degraded"] = True
            except Exception:
                pass
        
        # From governance_logs
        gov_log_path = os.path.join(self.artifacts_root, "governance_logs", f"{task_id}.json")
        if os.path.exists(gov_log_path):
            try:
                with open(gov_log_path, "r", encoding="utf-8") as f:
                    gov_log = json.load(f)
                    if isinstance(gov_log, list):
                        governance_info["decisions"].extend(gov_log)
            except Exception:
                pass
        
        return governance_info
    
    def load_plan_or_dag(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Load execution plan or DAG information
        
        Tries:
        - artifacts/rag_project/{task_id}/system_trace.json (execution_plan)
        - artifacts/learning/dag_mutations/{task_id}.json
        """
        plan_info = None
        
        # From system_trace.json
        system_trace_path = os.path.join(self.rag_project_dir, task_id, "system_trace.json")
        if os.path.exists(system_trace_path):
            try:
                with open(system_trace_path, "r", encoding="utf-8") as f:
                    trace = json.load(f)
                    execution_plan = trace.get("execution_plan")
                    if execution_plan:
                        plan_info = execution_plan
            except Exception:
                pass
        
        # From DAG mutations
        dag_mutations_path = os.path.join(self.artifacts_root, "learning", "dag_mutations", f"{task_id}.json")
        if os.path.exists(dag_mutations_path):
            try:
                with open(dag_mutations_path, "r", encoding="utf-8") as f:
                    dag_mutations = json.load(f)
                    if plan_info is None:
                        plan_info = {}
                    plan_info["dag_mutations"] = dag_mutations
            except Exception:
                pass
        
        return plan_info
    
    def diff_tasks(self, task_a: str, task_b: str) -> Dict[str, Any]:
        """
        Diff two tasks (cost, decisions, artifacts)
        
        Returns structured diff suitable for UI display
        """
        diff = {
            "task_a": task_a,
            "task_b": task_b,
            "cost_diff": {},
            "decision_diff": {},
            "artifact_diff": {}
        }
        
        # Cost diff
        cost_a = self.load_cost(task_a)
        cost_b = self.load_cost(task_b)
        
        diff["cost_diff"] = {
            "total_cost_a": cost_a["total_cost"],
            "total_cost_b": cost_b["total_cost"],
            "delta": cost_b["total_cost"] - cost_a["total_cost"],
            "breakdown_a": cost_a["cost_breakdown"],
            "breakdown_b": cost_b["cost_breakdown"]
        }
        
        # Decision diff
        gov_a = self.load_governance(task_a)
        gov_b = self.load_governance(task_b)
        
        diff["decision_diff"] = {
            "degraded_a": gov_a["degraded"],
            "degraded_b": gov_b["degraded"],
            "decisions_count_a": len(gov_a["decisions"]),
            "decisions_count_b": len(gov_b["decisions"])
        }
        
        # Artifact diff
        artifacts_a = self._list_artifacts(task_a)
        artifacts_b = self._list_artifacts(task_b)
        
        diff["artifact_diff"] = {
            "only_in_a": sorted(list(set(artifacts_a) - set(artifacts_b))),
            "only_in_b": sorted(list(set(artifacts_b) - set(artifacts_a))),
            "in_both": sorted(list(set(artifacts_a) & set(artifacts_b)))
        }
        
        return diff
    
    def _list_artifacts(self, task_id: str) -> List[str]:
        """List all artifact files for a task"""
        artifacts = []
        
        task_dir = os.path.join(self.rag_project_dir, task_id)
        if os.path.exists(task_dir):
            try:
                for filename in os.listdir(task_dir):
                    artifacts.append(filename)
            except Exception:
                pass
        
        return artifacts

