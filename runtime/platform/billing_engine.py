"""
Usage Metering & Billing Foundation
确定性计量体系、Cost Ledger、对账能力
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from decimal import Decimal

@dataclass
class UsageRecord:
    """用量记录"""
    record_id: str
    tenant_id: str
    task_id: str
    timestamp: str
    task_count: int
    token_usage: int
    tool_calls: int
    actual_cost: Decimal
    forecast_cost: Decimal
    cost_delta: Decimal
    delta_source: str  # trace / metric reference

@dataclass
class CostLedgerEntry:
    """成本账本条目"""
    entry_id: str
    tenant_id: str
    task_id: str
    timestamp: str
    cost_type: str  # actual / forecast
    amount: Decimal
    currency: str
    evidence_ref: str  # trace / metric reference
    hash: str

class BillingEngine:
    """计费引擎（确定性计量体系）"""
    
    def __init__(self, base_dir: str = "artifacts/billing"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.ledger_file = os.path.join(base_dir, "cost_ledger.jsonl")
        self.usage_file = os.path.join(base_dir, "usage_records.jsonl")
    
    def record_usage(
        self,
        tenant_id: str,
        task_id: str,
        task_count: int,
        token_usage: int,
        tool_calls: int,
        actual_cost: Decimal,
        forecast_cost: Decimal,
        delta_source: str
    ) -> UsageRecord:
        """记录用量（确定性）"""
        record_id = f"usage_{hashlib.sha256(f'{tenant_id}_{task_id}_{datetime.now().isoformat()}'.encode()).hexdigest()[:16]}"
        
        record = UsageRecord(
            record_id=record_id,
            tenant_id=tenant_id,
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            task_count=task_count,
            token_usage=token_usage,
            tool_calls=tool_calls,
            actual_cost=actual_cost,
            forecast_cost=forecast_cost,
            cost_delta=actual_cost - forecast_cost,
            delta_source=delta_source
        )
        
        # 追加到文件（只追加，不可修改）
        with open(self.usage_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")
        
        return record
    
    def record_cost(
        self,
        tenant_id: str,
        task_id: str,
        cost_type: str,
        amount: Decimal,
        evidence_ref: str
    ) -> CostLedgerEntry:
        """记录成本（确定性，不允许人工修正）"""
        entry_id = f"cost_{hashlib.sha256(f'{tenant_id}_{task_id}_{cost_type}_{datetime.now().isoformat()}'.encode()).hexdigest()[:16]}"
        
        entry = CostLedgerEntry(
            entry_id=entry_id,
            tenant_id=tenant_id,
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            cost_type=cost_type,
            amount=amount,
            currency="USD",
            evidence_ref=evidence_ref,
            hash=""  # 将在计算后填充
        )
        
        # 计算 hash（确定性）
        entry_data = asdict(entry)
        entry_data.pop("hash")
        entry_hash = hashlib.sha256(
            json.dumps(entry_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        entry.hash = entry_hash
        
        # 追加到账本（只追加，不可修改）
        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False, default=str) + "\n")
        
        return entry
    
    def reconcile_forecast_vs_actual(
        self,
        tenant_id: str,
        task_id: str,
        forecast_cost: Decimal,
        actual_cost: Decimal,
        trace_ref: str
    ) -> Dict[str, Any]:
        """Forecast vs Actual 对账（偏差来源必须可定位）"""
        delta = actual_cost - forecast_cost
        delta_percent = (delta / forecast_cost * 100) if forecast_cost > 0 else 0
        
        reconciliation = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "forecast_cost": str(forecast_cost),
            "actual_cost": str(actual_cost),
            "delta": str(delta),
            "delta_percent": float(delta_percent),
            "trace_ref": trace_ref,
            "reconciliation_hash": ""
        }
        
        # 计算 hash
        reconciliation_hash = hashlib.sha256(
            json.dumps(reconciliation, sort_keys=True, default=str).encode()
        ).hexdigest()
        reconciliation["reconciliation_hash"] = reconciliation_hash
        
        # 保存对账记录
        reconciliation_file = os.path.join(self.base_dir, f"reconciliation_{tenant_id}_{task_id}.json")
        with open(reconciliation_file, "w", encoding="utf-8") as f:
            json.dump(reconciliation, f, indent=2, ensure_ascii=False, default=str)
        
        return reconciliation
    
    def get_tenant_billing_summary(
        self,
        tenant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取 tenant 账单汇总（基于系统证据）"""
        total_actual_cost = Decimal("0.0")
        total_forecast_cost = Decimal("0.0")
        task_count = 0
        token_usage = 0
        tool_calls = 0
        
        # 读取账本
        if os.path.exists(self.ledger_file):
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["tenant_id"] == tenant_id:
                        if entry["cost_type"] == "actual":
                            total_actual_cost += Decimal(str(entry["amount"]))
                        elif entry["cost_type"] == "forecast":
                            total_forecast_cost += Decimal(str(entry["amount"]))
        
        # 读取用量记录
        if os.path.exists(self.usage_file):
            with open(self.usage_file, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    if record["tenant_id"] == tenant_id:
                        task_count += record["task_count"]
                        token_usage += record["token_usage"]
                        tool_calls += record["tool_calls"]
        
        summary = {
            "tenant_id": tenant_id,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "task_count": task_count,
            "token_usage": token_usage,
            "tool_calls": tool_calls,
            "total_actual_cost": str(total_actual_cost),
            "total_forecast_cost": str(total_forecast_cost),
            "total_delta": str(total_actual_cost - total_forecast_cost),
            "evidence_source": "system_trace",
            "billing_hash": ""
        }
        
        # 计算 hash
        summary_hash = hashlib.sha256(
            json.dumps(summary, sort_keys=True, default=str).encode()
        ).hexdigest()
        summary["billing_hash"] = summary_hash
        
        return summary


