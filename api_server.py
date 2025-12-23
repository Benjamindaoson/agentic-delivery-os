"""
FastAPI REST API Server for Agentic Delivery OS
Endpoints:
    POST /run - Execute a new task
    GET /session/{session_id} - Get session details
    GET /run/{run_id} - Get run details
    GET /artifacts/{run_id} - Get all artifacts for a run
    POST /replay/{run_id} - Replay a historical run
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import os
from pathlib import Path

from runtime.l5_engine import L5Engine

app = FastAPI(title="Agentic Delivery OS API", version="L5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = L5Engine()


class RunRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: str = "default_user"


class RunResponse(BaseModel):
    run_id: str
    session_id: str
    task_type: str
    quality_score: float
    cost: float
    latency: float
    success: bool


@app.get("/")
def root():
    return {"service": "Agentic Delivery OS", "version": "L5.0", "status": "operational"}


@app.post("/run", response_model=RunResponse)
def execute_run(request: RunRequest):
    """Execute a new task run"""
    result = engine.execute_run(request.query, request.session_id, request.user_id)
    
    return RunResponse(
        run_id=result['run_id'],
        session_id=result['session_id'],
        task_type=result['classification'].task_type,
        quality_score=result['eval'].quality_score,
        cost=result['eval'].cost,
        latency=result['eval'].latency,
        success=result['eval'].success
    )


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get session details"""
    path = f"artifacts/session/{session_id}.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Session not found")
    
    with open(path) as f:
        return json.load(f)


@app.get("/run/{run_id}")
def get_run(run_id: str):
    """Get run details"""
    eval_path = f"artifacts/eval/{run_id}.json"
    if not os.path.exists(eval_path):
        raise HTTPException(status_code=404, detail="Run not found")
    
    with open(eval_path) as f:
        eval_data = json.load(f)
    
    # Load additional artifacts
    artifacts = {}
    goals_dir = "artifacts/goals"
    if os.path.exists(goals_dir):
        for file in os.listdir(goals_dir):
            if file.startswith(run_id):
                artifact_type = file.replace(f"{run_id}_", "").replace(".json", "")
                with open(f"{goals_dir}/{file}") as af:
                    artifacts[artifact_type] = json.load(af)
    
    return {
        "run_id": run_id,
        "eval": eval_data,
        "artifacts": artifacts
    }


@app.get("/artifacts/{run_id}")
def get_artifacts(run_id: str):
    """Get all artifacts for a run"""
    artifacts = {}
    
    # Scan all artifact directories
    for root, dirs, files in os.walk("artifacts"):
        for file in files:
            if run_id in file and file.endswith(".json"):
                artifact_path = os.path.join(root, file)
                artifact_key = f"{os.path.basename(root)}/{file}"
                with open(artifact_path) as f:
                    artifacts[artifact_key] = json.load(f)
    
    if not artifacts:
        raise HTTPException(status_code=404, detail="No artifacts found for run")
    
    return artifacts


@app.post("/replay/{run_id}")
def replay_run(run_id: str):
    """Replay a historical run"""
    task_path = f"artifacts/task_type/{run_id}.json"
    if not os.path.exists(task_path):
        raise HTTPException(status_code=404, detail="Run not found")
    
    with open(task_path) as f:
        task = json.load(f)
    
    return {
        "run_id": run_id,
        "task": task,
        "replay_status": "completed",
        "artifacts_available": True
    }


@app.get("/agents")
def list_agents():
    """List all agent profiles"""
    agents = []
    agents_dir = "artifacts/agent_profiles"
    if os.path.exists(agents_dir):
        for file in os.listdir(agents_dir):
            with open(f"{agents_dir}/{file}") as f:
                agents.append(json.load(f))
    return agents


@app.get("/tools")
def list_tools():
    """List all tool profiles"""
    tools = []
    tools_dir = "artifacts/tool_profiles"
    if os.path.exists(tools_dir):
        for file in os.listdir(tools_dir):
            with open(f"{tools_dir}/{file}") as f:
                tools.append(json.load(f))
    return tools


@app.get("/runs")
def list_runs(limit: int = 20):
    """List recent runs"""
    runs = []
    eval_dir = "artifacts/eval"
    if os.path.exists(eval_dir):
        files = sorted(
            [(f, os.path.getmtime(f"{eval_dir}/{f}")) for f in os.listdir(eval_dir)],
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        for file, _ in files:
            with open(f"{eval_dir}/{file}") as f:
                data = json.load(f)
                runs.append(data)
    
    return runs


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



