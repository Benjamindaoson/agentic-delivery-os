from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any
import os
import json
import uuid
import datetime

router = APIRouter()

WORKBENCH_ROOT = os.path.join("artifacts", "workbench")
os.makedirs(WORKBENCH_ROOT, exist_ok=True)
PROJECTS_PATH = os.path.join(WORKBENCH_ROOT, "projects.json")
RUNS_PATH = os.path.join(WORKBENCH_ROOT, "runs.json")

def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_json(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure_store():
    if not os.path.exists(PROJECTS_PATH):
        _write_json(PROJECTS_PATH, {})
    if not os.path.exists(RUNS_PATH):
        _write_json(RUNS_PATH, {})

@router.post("/projects")
async def create_project(name: str = Form(...)) -> Dict[str, Any]:
    """Create a new project"""
    _ensure_store()
    projects = _read_json(PROJECTS_PATH)
    project_id = str(uuid.uuid4())
    projects[project_id] = {
        "id": project_id,
        "name": name,
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    _write_json(PROJECTS_PATH, projects)
    # create project artifacts dir
    os.makedirs(os.path.join(WORKBENCH_ROOT, "projects", project_id), exist_ok=True)
    return projects[project_id]


@router.get("/projects")
async def list_projects() -> Dict[str, Any]:
    """列出所有项目（返回 id -> project map）"""
    _ensure_store()
    return _read_json(PROJECTS_PATH)


@router.get("/runs")
async def list_runs() -> Dict[str, Any]:
    """列出所有 runs（返回 id -> run map）"""
    _ensure_store()
    return _read_json(RUNS_PATH)

@router.post("/projects/{project_id}/ingest")
async def ingest_files(project_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Accept a single file upload and create an ingest run"""
    _ensure_store()
    projects = _read_json(PROJECTS_PATH)
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="project not found")
    runs = _read_json(RUNS_PATH)
    run_id = str(uuid.uuid4())
    run = {
        "id": run_id,
        "project_id": project_id,
        "type": "ingest",
        "status": "processing",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "file_name": file.filename,
        "logs": []
    }
    # save uploaded file
    proj_dir = os.path.join(WORKBENCH_ROOT, "projects", project_id)
    os.makedirs(proj_dir, exist_ok=True)
    dest_path = os.path.join(proj_dir, f"{run_id}-{file.filename}")
    with open(dest_path, "wb") as out_f:
        content = await file.read()
        out_f.write(content)
    run["logs"].append(f"Saved file to {dest_path}")
    # Mark run complete (for MVP we do synchronous ingest)
    run["status"] = "completed"
    run["completed_at"] = datetime.datetime.utcnow().isoformat()
    runs[run_id] = run
    _write_json(RUNS_PATH, runs)
    return run

@router.post("/projects/{project_id}/query")
async def query_project(project_id: str, query: str = Form(...)) -> Dict[str, Any]:
    """Run a simple query against project and produce an answer + evidence (mocked)"""
    _ensure_store()
    projects = _read_json(PROJECTS_PATH)
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="project not found")
    runs = _read_json(RUNS_PATH)
    run_id = str(uuid.uuid4())
    # Produce a minimal answer + evidence pack for MVP
    evidence = [
        {
            "id": str(uuid.uuid4()),
            "source": "uploaded_doc.pdf",
            "page": 1,
            "snippet": "Example snippet matching query",
            "score": 0.92,
            "rule_status": "ok"
        }
    ]
    run = {
        "id": run_id,
        "project_id": project_id,
        "type": "query",
        "status": "completed",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "query": query,
        "answer": "This is a mocked answer for the query.",
        "evidence": evidence,
        "latency_ms": 120,
        "cost": {"estimate": 0.001}
    }
    runs[run_id] = run
    _write_json(RUNS_PATH, runs)
    return run

@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> Dict[str, Any]:
    _ensure_store()
    runs = _read_json(RUNS_PATH)
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="run not found")
    return runs[run_id]

@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    _ensure_store()
    runs = _read_json(RUNS_PATH)
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="run not found")
    # return logs as plain JSON
    return JSONResponse(content={"logs": runs[run_id].get("logs", [])})

@router.post("/runs/{run_id}/replay")
async def replay_run(run_id: str):
    _ensure_store()
    runs = _read_json(RUNS_PATH)
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="run not found")
    # replay relies on artifacts/rag_project/<task_id> previously recorded traces
    # For MVP attempt to call existing replay runner if artifacts exist
    try:
        from runtime.replay.replay_runner import replay_task
    except Exception:
        raise HTTPException(status_code=500, detail="Replay runner not available")
    # Map run_id to artifact task id if present; for MVP assume task-golden or run_id
    task_id = runs[run_id].get("task_id", "task-golden")
    artifact_dir = os.path.join("artifacts", "rag_project", task_id)
    if not os.path.isdir(artifact_dir):
        raise HTTPException(status_code=404, detail=f"artifact directory not found for task {task_id}")
    report = replay_task(task_id)
    return report


