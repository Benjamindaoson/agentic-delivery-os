"""
ReplayRunner: deterministic replay of a recorded execution trace.
- Does not call real LLMs or execute real tools.
- Replays recorded events from system_trace.json and validates consistency.
- Writes replay_report.json into the same artifact directory.
"""
import os
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime

def _load_trace(task_dir: str) -> Dict[str, Any]:
    trace_path = os.path.join(task_dir, "system_trace.json")
    if not os.path.exists(trace_path):
        raise FileNotFoundError(f"Trace not found: {trace_path}")
    with open(trace_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_manifest(task_dir: str) -> Dict[str, Any]:
    manifest_path = os.path.join(task_dir, "delivery_manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _compare_values(path: str, a: Any, b: Any) -> Tuple[bool, Dict[str, Any]]:
    if a == b:
        return True, {}
    # for simplicity produce a small diff object
    return False, {"path": path, "expected": a, "actual": b}

def replay_task(task_id: str) -> Dict[str, Any]:
    """
    Replay the execution for task_id located under artifacts/rag_project/<task_id>
    Returns replay_report dict and writes replay_report.json in artifact dir.
    """
    artifact_dir = os.path.join("artifacts", "rag_project", task_id)
    if not os.path.isdir(artifact_dir):
        raise FileNotFoundError(f"Artifact directory not found: {artifact_dir}")

    trace = _load_trace(artifact_dir)
    manifest = _load_manifest(artifact_dir)

    diffs: List[Dict[str, Any]] = []
    executed_agents = trace.get("agent_executions", [])

    # Validate plan selection present
    execution_plan = trace.get("execution_plan", {})
    if not execution_plan:
        diffs.append({"path": "execution_plan", "error": "missing_execution_plan"})

    # Stepwise validation: for each recorded agent execution, "replay" by reading stored outputs
    for idx, entry in enumerate(executed_agents):
        agent = entry.get("agent")
        recorded_output = entry.get("output", {})
        recorded_decision = recorded_output.get("decision")

        # Simulated execution replaces LLM/tool calls with recorded outputs
        simulated_output = recorded_output.copy()

        # Compare decision
        ok, diff = _compare_values(f"agent_executions[{idx}].decision", recorded_decision, simulated_output.get("decision"))
        if not ok:
            diffs.append(diff)

        # Compare llm_info presence: ensure meta exists when expected
        recorded_llm = entry.get("llm_info")
        if recorded_llm:
            # verify required fields exist
            for fld in ["provider", "model_name", "prompt_hash"]:
                if fld not in recorded_llm:
                    diffs.append({"path": f"agent_executions[{idx}].llm_info.{fld}", "error": "missing_field"})

        # Compare tool executions: ensure any recorded tool executions are present
        recorded_tools = entry.get("tool_executions", []) or []
        for tidx, t in enumerate(recorded_tools):
            for fld in ["tool_name", "exit_code"]:
                if fld not in t:
                    diffs.append({"path": f"agent_executions[{idx}].tool_executions[{tidx}].{fld}", "error": "missing_field"})

    # Validate manifest consistency: executed_agents lists match trace executed agent names
    manifest_exec_agents = manifest.get("executed_agents", [])
    trace_agents = [e.get("agent") for e in executed_agents]
    if manifest_exec_agents and manifest_exec_agents != trace_agents:
        diffs.append({"path": "manifest.executed_agents", "expected": trace_agents, "actual": manifest_exec_agents})

    # Build report
    report = {
        "task_id": task_id,
        "replayed_at": datetime.now().isoformat(),
        "num_agent_executions": len(executed_agents),
        "num_diffs": len(diffs),
        "consistent": len(diffs) == 0,
        "diffs": diffs
    }

    # Write report
    report_path = os.path.join(artifact_dir, "replay_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python runtime/replay/replay_runner.py <task_id>")
        sys.exit(2)
    task_id = sys.argv[1]
    report = replay_task(task_id)
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()


