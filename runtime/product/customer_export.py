"""
Commercial Delivery & Customer Package
Customer-facing Export Bundle & Audit Bundle
"""
import os
import json
import zipfile
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

class CustomerExport:
    """客户导出包"""
    
    def __init__(self, base_dir: str = "artifacts/exports"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def create_customer_bundle(
        self,
        task_id: str,
        tenant_id: str,
        include_internal: bool = False
    ) -> str:
        """创建客户面向导出包（不含内部策略细节）"""
        bundle_dir = os.path.join(self.base_dir, f"customer_{task_id}")
        os.makedirs(bundle_dir, exist_ok=True)
        
        # 加载任务数据
        task_data = self._load_task_data(task_id, tenant_id)
        
        # 1. 执行结果
        execution_result = {
            "task_id": task_id,
            "status": task_data.get("status", {}).get("state"),
            "completion_time": task_data.get("created_at"),
            "cost": task_data.get("execution_overview", {}).get("total_cost", 0.0)
        }
        with open(os.path.join(bundle_dir, "execution_result.json"), "w", encoding="utf-8") as f:
            json.dump(execution_result, f, indent=2, ensure_ascii=False)
        
        # 2. Replay（event-order replay）
        replay_view = self._load_replay_view(task_id)
        with open(os.path.join(bundle_dir, "replay_view.json"), "w", encoding="utf-8") as f:
            json.dump(replay_view, f, indent=2, ensure_ascii=False)
        
        # 3. Cost
        cost_summary = {
            "task_id": task_id,
            "total_cost": task_data.get("execution_overview", {}).get("total_cost", 0.0),
            "cost_breakdown": self._get_cost_breakdown(task_data)
        }
        with open(os.path.join(bundle_dir, "cost_summary.json"), "w", encoding="utf-8") as f:
            json.dump(cost_summary, f, indent=2, ensure_ascii=False)
        
        # 4. 不含内部策略细节（不包含 governance_decisions 详细内容）
        
        # 创建 ZIP
        bundle_path = os.path.join(self.base_dir, f"customer_bundle_{task_id}.zip")
        with zipfile.ZipFile(bundle_path, "w") as zipf:
            for file in os.listdir(bundle_dir):
                file_path = os.path.join(bundle_dir, file)
                if os.path.isfile(file_path):
                    zipf.write(file_path, file)
        
        return bundle_path
    
    def create_audit_bundle(
        self,
        task_id: str,
        tenant_id: str
    ) -> str:
        """创建审计包（只读，包含 trace、decision、hash、evaluation reference）"""
        bundle_dir = os.path.join(self.base_dir, f"audit_{task_id}")
        os.makedirs(bundle_dir, exist_ok=True)
        
        # 加载完整 trace
        trace_data = self._load_full_trace(task_id, tenant_id)
        
        # 1. Trace
        with open(os.path.join(bundle_dir, "trace.json"), "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
        
        # 2. Decision
        decisions = trace_data.get("governance_decisions", [])
        with open(os.path.join(bundle_dir, "decisions.json"), "w", encoding="utf-8") as f:
            json.dump(decisions, f, indent=2, ensure_ascii=False)
        
        # 3. Hash
        trace_hash = hashlib.sha256(
            json.dumps(trace_data, sort_keys=True).encode()
        ).hexdigest()
        with open(os.path.join(bundle_dir, "trace_hash.txt"), "w", encoding="utf-8") as f:
            f.write(f"sha256:{trace_hash}\n")
        
        # 4. Evaluation reference
        evaluation_ref = {
            "task_id": task_id,
            "evaluation_run_id": trace_data.get("evaluation_run_id"),
            "evaluation_case_path": f"artifacts/phase7/cases/{task_id}/full_system/"
        }
        with open(os.path.join(bundle_dir, "evaluation_reference.json"), "w", encoding="utf-8") as f:
            json.dump(evaluation_ref, f, indent=2, ensure_ascii=False)
        
        # 创建 ZIP（只读）
        bundle_path = os.path.join(self.base_dir, f"audit_bundle_{task_id}.zip")
        with zipfile.ZipFile(bundle_path, "w") as zipf:
            for file in os.listdir(bundle_dir):
                file_path = os.path.join(bundle_dir, file)
                if os.path.isfile(file_path):
                    zipf.write(file_path, file)
        
        # 设置只读权限（简化：实际应该在文件系统层面设置）
        
        return bundle_path
    
    def _load_task_data(self, task_id: str, tenant_id: str) -> Dict[str, Any]:
        """加载任务数据"""
        task_path = os.path.join("artifacts", "tenants", tenant_id, "tasks", task_id, "system_trace.json")
        if os.path.exists(task_path):
            with open(task_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _load_replay_view(self, task_id: str) -> Dict[str, Any]:
        """加载 replay view"""
        replay_path = os.path.join("artifacts", "phase7", "cases", task_id, "full_system", "replay_view.json")
        if os.path.exists(replay_path):
            with open(replay_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _load_full_trace(self, task_id: str, tenant_id: str) -> Dict[str, Any]:
        """加载完整 trace"""
        return self._load_task_data(task_id, tenant_id)
    
    def _get_cost_breakdown(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """获取成本分解"""
        agent_reports = task_data.get("agent_reports", [])
        breakdown = {}
        for report in agent_reports:
            agent_name = report.get("agent", "unknown")
            cost = report.get("cost_impact", 0.0)
            breakdown[agent_name] = breakdown.get(agent_name, 0.0) + cost
        return breakdown


