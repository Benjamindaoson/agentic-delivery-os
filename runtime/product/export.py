"""
Export & Compare: 导出/对比/交付包
结构化、可 hash、可验证完整性
"""
import os
import json
import hashlib
import zipfile
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

@dataclass
class ExportManifest:
    """导出清单"""
    task_id: str
    export_hash: str
    created_at: str
    files: List[str]

class ExportEngine:
    """导出引擎（结构化、可hash）"""
    
    def __init__(self):
        self.version = "1.0"
    
    def export_task(
        self,
        task_id: str,
        trace_data: Dict[str, Any],
        output_dir: str = "exports"
    ) -> ExportManifest:
        """导出任务交付包"""
        export_dir = os.path.join(output_dir, f"task_{task_id}")
        os.makedirs(export_dir, exist_ok=True)
        
        files = []
        
        # 1. trace_summary.json
        from runtime.platform.trace_store import TraceStore
        trace_store = TraceStore()
        summary = trace_store.load_summary(task_id)
        if summary:
            summary_path = os.path.join(export_dir, "trace_summary.json")
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(asdict(summary), f, indent=2, ensure_ascii=False)
            files.append("trace_summary.json")
        
        # 2. execution_plan.json
        execution_plan = trace_data.get("execution_plan", {})
        plan_path = os.path.join(export_dir, "execution_plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(execution_plan, f, indent=2, ensure_ascii=False)
        files.append("execution_plan.json")
        
        # 3. governance_decisions.json
        governance_decisions = trace_data.get("governance_decisions", [])
        gov_path = os.path.join(export_dir, "governance_decisions.json")
        with open(gov_path, "w", encoding="utf-8") as f:
            json.dump(governance_decisions, f, indent=2, ensure_ascii=False)
        files.append("governance_decisions.json")
        
        # 4. summary.json（分层摘要）
        from runtime.expression.summary import HierarchicalSummaryEngine
        summary_engine = HierarchicalSummaryEngine()
        summary_output = summary_engine.summarize(trace_data)
        summary_path = os.path.join(export_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump({
                "level_0": [asdict(item) for item in summary_output.level_0],
                "level_1": [asdict(item) for item in summary_output.level_1],
                "level_2": [asdict(item) for item in summary_output.level_2],
                "summary_version": summary_output.summary_version,
                "summary_hash": summary_output.summary_hash
            }, f, indent=2, ensure_ascii=False)
        files.append("summary.json")
        
        # 5. narrative.json（叙事）
        narratives = []
        for decision in governance_decisions:
            execution_mode = decision.get("execution_mode", "normal")
            trigger = decision.get("trigger")
            from runtime.expression.narrative import NarrativeEngine, NarrativeInput
            narrative_engine = NarrativeEngine()
            try:
                narrative_input = NarrativeInput(
                    governance_decision=execution_mode,
                    trigger=trigger
                )
                narrative_output = narrative_engine.generate(narrative_input)
                narratives.append({
                    "narrative_id": narrative_output.narrative_id,
                    "text": narrative_output.text,
                    "narrative_version": narrative_output.narrative_version,
                    "narrative_hash": narrative_output.narrative_hash
                })
            except ValueError:
                # 无匹配模板，跳过
                pass
        
        narrative_path = os.path.join(export_dir, "narrative.json")
        with open(narrative_path, "w", encoding="utf-8") as f:
            json.dump(narratives, f, indent=2, ensure_ascii=False)
        files.append("narrative.json")
        
        # 6. cost_report.json（成本报告）
        from runtime.product.cost_accounting import CostAccountingEngine
        cost_engine = CostAccountingEngine()
        # 简化：假设已有预测
        cost_report = {
            "actual_tokens": sum(
                r.get("signals", {}).get("tokens_used", 0)
                for r in trace_data.get("agent_reports", [])
            ),
            "actual_usd": sum(
                r.get("cost_impact", 0.0)
                for r in trace_data.get("agent_reports", [])
            )
        }
        cost_path = os.path.join(export_dir, "cost_report.json")
        with open(cost_path, "w", encoding="utf-8") as f:
            json.dump(cost_report, f, indent=2, ensure_ascii=False)
        files.append("cost_report.json")
        
        # 7. manifest.json（清单）
        # 计算导出 hash
        all_content = ""
        for file in files:
            file_path = os.path.join(export_dir, file)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    all_content += f.read()
        
        export_hash = hashlib.sha256(all_content.encode()).hexdigest()
        
        manifest = ExportManifest(
            task_id=task_id,
            export_hash=export_hash,
            created_at=datetime.now().isoformat(),
            files=files
        )
        
        manifest_path = os.path.join(export_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)
        
        return manifest
    
    def compare_tasks(
        self,
        task_id_a: str,
        task_id_b: str
    ) -> Dict[str, Any]:
        """对比两个任务（确定性规则）"""
        # 加载两个任务的 trace
        import os
        trace_path_a = os.path.join("artifacts", "rag_project", task_id_a, "system_trace.json")
        trace_path_b = os.path.join("artifacts", "rag_project", task_id_b, "system_trace.json")
        
        trace_data_a = {}
        trace_data_b = {}
        
        if os.path.exists(trace_path_a):
            with open(trace_path_a, "r", encoding="utf-8") as f:
                trace_data_a = json.load(f)
        
        if os.path.exists(trace_path_b):
            with open(trace_path_b, "r", encoding="utf-8") as f:
                trace_data_b = json.load(f)
        
        # 对比路径差异
        plan_a = trace_data_a.get("execution_plan", {}).get("plan_selection_history", [])
        plan_b = trace_data_b.get("execution_plan", {}).get("plan_selection_history", [])
        
        # 对比成本差异
        cost_a = sum(r.get("cost_impact", 0.0) for r in trace_data_a.get("agent_reports", []))
        cost_b = sum(r.get("cost_impact", 0.0) for r in trace_data_b.get("agent_reports", []))
        
        # 对比失败类型差异
        failure_a = trace_data_a.get("evaluation_feedback_flow", {}).get("last_failure_type")
        failure_b = trace_data_b.get("evaluation_feedback_flow", {}).get("last_failure_type")
        
        # 对比关键决策点差异
        decisions_a = [
            d.get("execution_mode")
            for d in trace_data_a.get("governance_decisions", [])
        ]
        decisions_b = [
            d.get("execution_mode")
            for d in trace_data_b.get("governance_decisions", [])
        ]
        
        return {
            "task_id_a": task_id_a,
            "task_id_b": task_id_b,
            "path_differences": {
                "plan_a": [p.get("selected_plan_id") for p in plan_a],
                "plan_b": [p.get("selected_plan_id") for p in plan_b]
            },
            "cost_differences": {
                "cost_a": cost_a,
                "cost_b": cost_b,
                "delta": cost_b - cost_a
            },
            "failure_type_differences": {
                "failure_a": failure_a,
                "failure_b": failure_b
            },
            "decision_differences": {
                "decisions_a": decisions_a,
                "decisions_b": decisions_b
            },
            "compare_version": self.version,
            "compared_at": datetime.now().isoformat()
        }


