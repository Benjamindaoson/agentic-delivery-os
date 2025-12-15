from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import delivery, task
from backend.api import data_intel
from backend.orchestration import orchestrator

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await orchestrator.initialize()
    yield
    # Shutdown (if needed)

app = FastAPI(
    title="Agentic AI Delivery OS API",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(delivery.router, prefix="/api/delivery", tags=["delivery"])
app.include_router(task.router, prefix="/api/task", tags=["task"])
from backend.api import expression
app.include_router(expression.router, prefix="/api/expression", tags=["expression"])
app.include_router(data_intel.router, prefix="/api", tags=["data-intel"])

@app.get("/api/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # Use module path so imports resolve when launched via `python -m backend.main`
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)

