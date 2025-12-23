"""
Dataset Builder: 从 TraceStore 抽取训练样本
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from runtime.platform.trace_store import TraceStore


def build_training_examples(
    trace_store: TraceStore,
    *,
    since_ts: float | None = None,
    until_ts: float | None = None,
    max_examples: int = 1000
) -> List[Dict[str, Any]]:
    """
    从 TraceStore 中抽取可用于策略学习的训练样本。

    每条样本必须至少包含：
    - run_id
    - task_spec（原始任务输入）
    - selected_plan
    - governance_decisions
    - execution_outcome（success / failed / degraded）
    - cost_summary
    - timestamps

    返回结构必须是可 JSON 序列化的 dict list。
    """
    examples = []
    
    # 查询符合条件的 task_ids
    filter_params = {}
    if since_ts or until_ts:
        # 注意：trace_store.query_tasks 目前不支持时间范围，先查询所有
        # 然后在加载时过滤
        pass
    
    # 获取所有已索引的任务
    all_task_ids = trace_store.query_tasks(filter_params)
    
    # 如果索引为空，尝试从 summaries 目录读取
    if not all_task_ids:
        summaries_dir = trace_store.summaries_dir
        if os.path.exists(summaries_dir):
            for filename in os.listdir(summaries_dir):
                if filename.endswith('.json'):
                    task_id = filename[:-5]  # 移除 .json 后缀
                    all_task_ids.append(task_id)
    
    # 限制数量
    task_ids = all_task_ids[:max_examples]
    
    for task_id in task_ids:
        try:
            # 加载 trace summary
            summary = trace_store.load_summary(task_id)
            if not summary:
                continue
            
            # 加载完整 trace（通过加载 blob 或事件重构）
            # 为了获取完整信息，需要加载所有相关数据
            events, _ = trace_store.load_events(task_id, limit=1000)
            
            # 构建 trace_data 的简化版本（从 summary 和 events）
            trace_data = _reconstruct_trace_data(summary, events)
            
            # 检查时间范围
            if since_ts or until_ts:
                created_at_str = summary.created_at
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        created_ts = created_at.timestamp()
                        if since_ts and created_ts < since_ts:
                            continue
                        if until_ts and created_ts > until_ts:
                            continue
                    except (ValueError, AttributeError):
                        pass  # 如果时间解析失败，包含该样本
            
            # 构建训练样本
            example = _build_example_from_trace(task_id, trace_data, summary)
            if example:
                examples.append(example)
        except Exception as e:
            # 跳过有问题的 trace
            continue
    
    return examples


def _reconstruct_trace_data(summary: Any, events: List[Any]) -> Dict[str, Any]:
    """从 summary 和 events 重构 trace_data 结构"""
    trace_data = {
        "task_id": summary.task_id,
        "state_transitions": [],
        "agent_reports": [],
        "governance_decisions": [],
        "execution_plan": {},
        "evaluation_feedback_flow": {},
        "generated_at": summary.created_at or datetime.now().isoformat()
    }
    
    # 从 summary 提取信息
    if summary.current_plan_id:
        trace_data["execution_plan"] = {
            "plan_id": summary.current_plan_id,
            "plan_version": "1.0",  # 默认版本
            "path_type": summary.current_plan_path_type or "normal",
            "plan_selection_history": []
        }
    
    # 从 summary 提取 governance decisions（从 key_decisions_topk）
    for decision in summary.key_decisions_topk or []:
        if decision.get("type") == "governance_decision":
            trace_data["governance_decisions"].append({
                "execution_mode": decision.get("execution_mode", "normal"),
                "reasoning": decision.get("reasoning", ""),
                "timestamp": decision.get("timestamp")
            })
    
    # 从 events 提取更多信息
    for event in events:
        if event.type == "governance_decision" and event.payload:
            trace_data["governance_decisions"].append(event.payload)
        elif event.type == "agent_report" and event.payload:
            trace_data["agent_reports"].append(event.payload)
        elif event.type == "state_change" and event.payload:
            trace_data["state_transitions"].append(event.payload)
    
    # 确定最终状态
    final_state = summary.state
    trace_data["state_transitions"].append({
        "state": final_state,
        "timestamp": summary.updated_at or summary.created_at
    })
    
    return trace_data


def _build_example_from_trace(
    run_id: str,
    trace_data: Dict[str, Any],
    summary: Any
) -> Optional[Dict[str, Any]]:
    """从 trace_data 构建单个训练样本"""
    
    # 提取 selected_plan
    execution_plan = trace_data.get("execution_plan", {})
    selected_plan = {
        "plan_id": execution_plan.get("plan_id", "unknown"),
        "version": execution_plan.get("plan_version", "1.0")
    }
    
    # 提取 governance_decisions（规则触发和最终决策）
    governance_decisions = trace_data.get("governance_decisions", [])
    rules_triggered = []
    final_decision = "allow"
    
    for decision in governance_decisions:
        execution_mode = decision.get("execution_mode", "normal")
        rules_triggered.append({
            "mode": execution_mode,
            "reasoning": decision.get("reasoning", "")[:200]
        })
        if execution_mode != "normal":
            final_decision = execution_mode
        if execution_mode == "paused":
            final_decision = "abort"
    
    if not rules_triggered:
        # 如果没有明确的 governance decisions，从 summary 推断
        result_summary = summary.result_summary or {}
        if result_summary.get("has_paused"):
            final_decision = "abort"
        elif result_summary.get("has_degraded"):
            final_decision = "degrade"
    
    # 提取 execution_outcome
    state_transitions = trace_data.get("state_transitions", [])
    final_state = state_transitions[-1].get("state", "UNKNOWN") if state_transitions else "UNKNOWN"
    
    outcome_status = "success"
    failure_reason = None
    
    if final_state in ["FAILED", "ERROR"]:
        outcome_status = "failed"
        failure_reason = trace_data.get("evaluation_feedback_flow", {}).get("last_failure_type", "unknown")
    elif final_state in ["PAUSED", "CANCELLED"]:
        outcome_status = "degraded"
    elif final_decision in ["degraded", "minimal"]:
        outcome_status = "degraded"
    
    # 提取 cost_summary
    cost_summary = summary.cost_summary or {}
    agent_reports = trace_data.get("agent_reports", [])
    
    # 计算总 tokens（从 agent_reports）
    total_tokens = sum(
        r.get("signals", {}).get("tokens_used", 0)
        for r in agent_reports
    )
    
    # 计算 USD（简化：基于 tokens）
    total_usd = (total_tokens / 1000) * 0.002  # $0.002 per 1k tokens
    
    # 计算 latency（从 timestamps）
    start_ts = None
    end_ts = None
    if summary.created_at:
        try:
            start_ts = datetime.fromisoformat(summary.created_at.replace('Z', '+00:00')).timestamp()
        except (ValueError, AttributeError):
            pass
    if summary.updated_at:
        try:
            end_ts = datetime.fromisoformat(summary.updated_at.replace('Z', '+00:00')).timestamp()
        except (ValueError, AttributeError):
            pass
    
    latency_ms = None
    if start_ts and end_ts:
        latency_ms = int((end_ts - start_ts) * 1000)
    
    # 构建样本
    # 注意：task_spec 通常存储在 StateManager 中（context["spec"]），
    # 为了保持 dataset_builder 的独立性和同步性，这里留空。
    # 如果需要完整的 task_spec，可以在调用方通过 StateManager.get_task_context() 获取并合并。
    example = {
        "run_id": run_id,
        "task_spec": {},  # 需要从 StateManager 单独加载：state_manager.get_task_context(run_id).get("spec", {})
        "selected_plan": selected_plan,
        "governance": {
            "rules_triggered": rules_triggered,
            "final_decision": final_decision
        },
        "outcome": {
            "status": outcome_status,
            "failure_reason": failure_reason
        },
        "cost": {
            "tokens": total_tokens,
            "usd": total_usd,
            "latency_ms": latency_ms
        },
        "timestamps": {
            "start": start_ts or 0,
            "end": end_ts or 0
        }
    }
    
    return example


def export_training_dataset(
    examples: List[Dict[str, Any]],
    output_path: str
) -> None:
    """
    将训练样本导出为 jsonl 文件。
    一行一个样本，UTF-8 编码。
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for example in examples:
            json_line = json.dumps(example, ensure_ascii=False)
            f.write(json_line + "\n")

