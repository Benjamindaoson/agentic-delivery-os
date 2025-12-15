"""
Expression Layer API (Phase 5)
Salience / Summary / Narrative / Cost Accounting / Export
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from runtime.expression.salience import SalienceEngine, SalienceInput
from runtime.expression.summary import HierarchicalSummaryEngine
from runtime.expression.narrative import NarrativeEngine, NarrativeInput
from runtime.product.cost_accounting import CostAccountingEngine
from runtime.product.export import ExportEngine
import os
import json

router = APIRouter()

@router.post("/salience")
async def rank_salience(input_data: Dict[str, Any]):
    """显著性排序"""
    engine = SalienceEngine()
    salience_input = SalienceInput(**input_data)
    output = engine.rank(salience_input)
    return {
        "ranked_event_ids": output.ranked_event_ids,
        "salience_version": output.salience_version,
        "salience_hash": output.salience_hash
    }

@router.get("/{task_id}/summary")
async def get_summary(task_id: str):
    """获取分层摘要"""
    trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
    if not os.path.exists(trace_path):
        raise HTTPException(status_code=404, detail="Trace not found")
    
    with open(trace_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)
    
    engine = HierarchicalSummaryEngine()
    output = engine.summarize(trace_data)
    
    return {
        "level_0": [
            {"text": item.text, "evidence": item.evidence}
            for item in output.level_0
        ],
        "level_1": [
            {"text": item.text, "evidence": item.evidence}
            for item in output.level_1
        ],
        "level_2": [
            {"text": item.text, "evidence": item.evidence}
            for item in output.level_2
        ],
        "summary_version": output.summary_version,
        "summary_hash": output.summary_hash
    }

@router.post("/narrative")
async def generate_narrative(input_data: Dict[str, Any]):
    """生成叙事（确定映射）"""
    engine = NarrativeEngine()
    narrative_input = NarrativeInput(**input_data)
    try:
        output = engine.generate(narrative_input)
        return {
            "narrative_id": output.narrative_id,
            "text": output.text,
            "narrative_version": output.narrative_version,
            "narrative_hash": output.narrative_hash
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{task_id}/cost/predict")
async def predict_cost(task_id: str):
    """成本预测"""
    # 简化：从 spec 提取参数
    import os
    trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
    if not os.path.exists(trace_path):
        raise HTTPException(status_code=404, detail="Trace not found")
    
    with open(trace_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)
    
    # 提取参数（简化）
    spec = trace_data.get("final_context", {}).get("spec", {})
    spec_length = len(json.dumps(spec))
    node_count = len(trace_data.get("execution_plan", {}).get("executed_nodes", []))
    tool_call_count = len(trace_data.get("tool_executions", []))
    retry_count = sum(
        1 for r in trace_data.get("agent_reports", [])
        if r.get("llm_fallback_used", False)
    )
    
    from runtime.execution_plan.plan_definition import PlanPath
    path_type = PlanPath.NORMAL  # 简化
    
    engine = CostAccountingEngine()
    prediction = engine.predict(spec_length, node_count, tool_call_count, retry_count, path_type)
    
    return {
        "predicted_tokens": prediction.predicted_tokens,
        "predicted_usd": prediction.predicted_usd,
        "prediction_version": prediction.prediction_version,
        "prediction_hash": prediction.prediction_hash
    }

@router.get("/{task_id}/export")
async def export_task(task_id: str):
    """导出任务交付包"""
    trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
    if not os.path.exists(trace_path):
        raise HTTPException(status_code=404, detail="Trace not found")
    
    with open(trace_path, "r", encoding="utf-8") as f:
        trace_data = json.load(f)
    
    engine = ExportEngine()
    manifest = engine.export_task(task_id, trace_data)
    
    return {
        "task_id": manifest.task_id,
        "export_hash": manifest.export_hash,
        "created_at": manifest.created_at,
        "files": manifest.files,
        "export_dir": f"exports/task_{task_id}"
    }

@router.get("/compare")
async def compare_tasks(task_id_a: str, task_id_b: str):
    """对比两个任务"""
    engine = ExportEngine()
    comparison = engine.compare_tasks(task_id_a, task_id_b)
    return comparison


