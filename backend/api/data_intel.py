"""
Data Intelligence Agent API endpoints.
Read-only exposure: start run, fetch result.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
import json

from runtime.data_intel.executor import executor_singleton

router = APIRouter()


@router.post("/data-intel/run")
async def start_data_intel_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    input_files = payload.get("input_files", [])
    tenant_context = payload.get("tenant_context", {})
    tenant_policy = payload.get("tenant_policy")
    system_constraints = payload.get("system_constraints", {})
    runtime_capabilities = payload.get("runtime_capabilities", {})

    if not input_files:
        raise HTTPException(status_code=400, detail="input_files required")

    result = executor_singleton.run(
        input_files=input_files,
        tenant_context=tenant_context,
        tenant_policy=tenant_policy,
        system_constraints=system_constraints,
        runtime_capabilities=runtime_capabilities,
    )
    return {"run_id": result["run_id"]}


@router.get("/data-intel/run/{run_id}/result")
async def get_data_intel_result(run_id: str) -> Dict[str, Any]:
    run_dir = os.path.join("artifacts", "data_intel", run_id)
    evidence_path = os.path.join(run_dir, "evidence.json")
    if not os.path.exists(evidence_path):
        raise HTTPException(status_code=404, detail="run_id not found")
    with open(evidence_path, "r", encoding="utf-8") as f:
        evidence = json.load(f)
    return evidence
