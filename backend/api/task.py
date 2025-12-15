from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.schemas.task import TaskStatusResponse
from backend.orchestration import orchestrator
from runtime.platform.trace_store import TraceStore
from runtime.platform.event_stream import EventStream
import os
import json
import asyncio

router = APIRouter()

@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    status = await orchestrator.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status

@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取任务完整信息（包含执行总览）"""
    status = await orchestrator.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 读取 trace 获取执行信息
    trace = await _load_trace(task_id)
    context = await orchestrator.state_manager.get_task_context(task_id)
    
    # 提取执行总览信息
    execution_plan = trace.get("execution_plan", {}) if trace else {}
    governance_decisions = trace.get("governance_decisions", []) if trace else []
    
    # 判断是否发生降级/暂停
    has_degraded = any(
        d.get("execution_mode") in ["degraded", "minimal"] 
        for d in governance_decisions
    )
    has_paused = any(
        d.get("execution_mode") == "paused" 
        for d in governance_decisions
    )
    
    # 计算累计成本
    agent_reports = trace.get("agent_reports", []) if trace else []
    total_cost = sum(r.get("cost_impact", 0.0) for r in agent_reports)
    
    return {
        "task_id": task_id,
        "status": status,
        "execution_overview": {
            "current_plan": execution_plan.get("path_type"),
            "plan_id": execution_plan.get("plan_id"),
            "current_node": status.progress.currentAgent if status.progress else None,
            "total_cost": total_cost,
            "has_degraded": has_degraded,
            "has_paused": has_paused,
            "executed_nodes_count": len(execution_plan.get("executed_nodes", []))
        },
        "created_at": context.get("created_at") if context else None
    }

@router.get("/{task_id}/events")
async def get_task_events(task_id: str):
    """获取任务事件流（系统时间线）"""
    trace = await _load_trace(task_id)
    if not trace:
        raise HTTPException(status_code=404, detail="任务不存在或未开始执行")
    
    events = []
    
    # Agent 执行事件
    for agent_exec in trace.get("agent_executions", []):
        events.append({
            "type": "agent_execution",
            "timestamp": agent_exec.get("timestamp"),
            "agent": agent_exec.get("agent"),
            "status": agent_exec.get("status"),
            "decision": agent_exec.get("output", {}).get("decision")
        })
    
    # Governance 决策事件
    for gov_decision in trace.get("governance_decisions", []):
        events.append({
            "type": "governance_decision",
            "timestamp": gov_decision.get("timestamp"),
            "checkpoint": gov_decision.get("checkpoint"),
            "execution_mode": gov_decision.get("execution_mode"),
            "reasoning": gov_decision.get("reasoning")
        })
    
    # ExecutionPlan 切换事件
    for plan_selection in trace.get("execution_plan", {}).get("plan_selection_history", []):
        events.append({
            "type": "plan_selection",
            "timestamp": plan_selection.get("timestamp"),
            "selected_plan_id": plan_selection.get("selected_plan_id"),
            "path_type": plan_selection.get("path_type"),
            "reasoning": plan_selection.get("reasoning"),
            "trigger": plan_selection.get("trigger")
        })
    
    # 按时间排序
    events.sort(key=lambda x: x.get("timestamp", ""))
    
    return {"events": events}

@router.get("/{task_id}/trace")
async def get_task_trace(task_id: str):
    """获取完整 trace（用于详细分析）"""
    trace = await _load_trace(task_id)
    if not trace:
        raise HTTPException(status_code=404, detail="任务不存在或未开始执行")
    return trace

@router.post("/{task_id}/input")
async def submit_task_input(task_id: str, input_data: Dict[str, Any]):
    """提交用户输入（用于 PAUSED 场景补齐信息）"""
    # 验证任务状态
    status = await orchestrator.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    if status.state != "PAUSED":
        raise HTTPException(status_code=400, detail="任务未处于 PAUSED 状态")
    
    # 更新上下文
    context = await orchestrator.state_manager.get_task_context(task_id)
    updated_context = {**context, **input_data}
    updated_context["user_supplied_patch"] = input_data
    updated_context["user_input_timestamp"] = datetime.now().isoformat()
    
    await orchestrator.state_manager.update_task_context(task_id, updated_context)
    
    return {"status": "input_received", "task_id": task_id}

@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务执行（PAUSED → RUNNING）"""
    status = await orchestrator.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    if status.state != "PAUSED":
        raise HTTPException(status_code=400, detail="任务未处于 PAUSED 状态")
    
    # 记录 resume 事件
    context = await orchestrator.state_manager.get_task_context(task_id)
    context["resume_event"] = {
        "timestamp": datetime.now().isoformat(),
        "resumed_from": "PAUSED"
    }
    await orchestrator.state_manager.update_task_context(task_id, context)
    
    # 更新状态并继续执行
    await orchestrator.state_manager.update_task_state(
        task_id,
        "SPEC_READY",
        reason="User resumed from PAUSED"
    )
    await orchestrator.start_execution(task_id)
    
    return {"status": "resumed", "task_id": task_id}

@router.post("/{task_id}/manual_decision")
async def submit_manual_decision(task_id: str, decision: Dict[str, Any]):
    """提交人工决策（MANUAL_TAKEOVER 场景）"""
    status = await orchestrator.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    decision_type = decision.get("decision")  # "continue_minimal", "continue_degraded", "stop"
    
    # 记录人工决策事件
    context = await orchestrator.state_manager.get_task_context(task_id)
    context["manual_decision_event"] = {
        "timestamp": datetime.now().isoformat(),
        "decision": decision_type,
        "reason": decision.get("reason")
    }
    await orchestrator.state_manager.update_task_context(task_id, context)
    
    if decision_type == "stop":
        await orchestrator.state_manager.update_task_state(
            task_id,
            "FAILED",
            reason=f"Manual decision: {decision_type}"
        )
        return {"status": "stopped", "task_id": task_id}
    else:
        # 继续执行（使用指定路径）
        # 注意：这里不直接修改 ExecutionPlan，而是通过 context 传递决策
        context["manual_execution_mode"] = "minimal" if decision_type == "continue_minimal" else "degraded"
        await orchestrator.state_manager.update_task_context(task_id, context)
        
        await orchestrator.state_manager.update_task_state(
            task_id,
            "SPEC_READY",
            reason=f"Manual decision: {decision_type}"
        )
        await orchestrator.start_execution(task_id)
        
        return {"status": "continued", "task_id": task_id, "mode": context["manual_execution_mode"]}

async def _load_trace(task_id: str) -> Optional[Dict[str, Any]]:
    """加载 system_trace.json"""
    trace_path = os.path.join("artifacts", "rag_project", task_id, "system_trace.json")
    if os.path.exists(trace_path):
        with open(trace_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# Phase 4: TraceStore API
trace_store = TraceStore()
event_stream = EventStream(trace_store)

@router.get("/{task_id}/trace/summary")
async def get_trace_summary(task_id: str):
    """获取 trace 摘要（Phase 4）"""
    summary = trace_store.load_summary(task_id)
    if not summary:
        # 如果没有摘要，尝试从完整 trace 构建
        trace_data = await _load_trace(task_id)
        if trace_data:
            summary = trace_store.build_summary_from_trace(task_id, trace_data)
            trace_store.save_summary(summary)
        else:
            raise HTTPException(status_code=404, detail="Trace not found")
    
    from runtime.platform.trace_store import TraceSummary
    return {
        "task_id": summary.task_id,
        "state": summary.state,
        "current_plan_id": summary.current_plan_id,
        "current_plan_path_type": summary.current_plan_path_type,
        "key_decisions_topk": summary.key_decisions_topk,
        "cost_summary": summary.cost_summary,
        "result_summary": summary.result_summary,
        "created_at": summary.created_at,
        "updated_at": summary.updated_at
    }

@router.get("/{task_id}/trace/events")
async def get_trace_events(
    task_id: str,
    cursor: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """获取 trace 事件（分页/游标）（Phase 4）"""
    events, next_cursor = trace_store.load_events(task_id, cursor=cursor, limit=limit)
    return {
        "events": [
            {
                "event_id": e.event_id,
                "task_id": e.task_id,
                "ts": e.ts,
                "type": e.type,
                "payload_ref": e.payload_ref,
                "payload": e.payload
            }
            for e in events
        ],
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None
    }

@router.get("/{task_id}/trace/blobs/{blob_id}")
async def get_trace_blob(task_id: str, blob_id: str):
    """获取 trace 大对象（Phase 4）"""
    blob = trace_store.load_blob(task_id, blob_id)
    if not blob:
        raise HTTPException(status_code=404, detail="Blob not found")
    return {
        "blob_id": blob.blob_id,
        "task_id": blob.task_id,
        "blob_type": blob.blob_type,
        "content": blob.content,
        "created_at": blob.created_at
    }

@router.get("/{task_id}/events/stream")
async def stream_events(task_id: str, cursor: Optional[str] = Query(None)):
    """SSE 事件流（Phase 4）"""
    async def event_generator():
        async for event_data in event_stream.stream_events(task_id, cursor=cursor):
            yield event_data
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

