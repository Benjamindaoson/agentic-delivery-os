# Phase 8 Repo Scan (Step 1)

## Scope & Inputs
- Repo root: backend/, runtime/, frontend/, scripts/, tests/, configs/, docs/, docker-compose.yml, Dockerfile.
- Current commands verified: `npm run build` (frontend) ✅, `python -m pytest -q` ✅ (with backend autostart fixture), backend can start via `python -m uvicorn backend.main:app` (with PYTHONPATH).

## Entrypoints (current)
- Backend: `backend/main.py` (FastAPI), health at `/api/health`.
- Frontend: Vite app (`frontend/`), build succeeds.
- Tests: `python -m pytest -q` (root conftest autostarts backend via uvicorn).
- Start scripts: `start_backend.sh/.bat` exist; no unified make targets yet.

## Pipeline Coverage (current)
- Offline RAG pipeline: basic delivery artifacts and RAG worker; no explicit ingestion/parse/ocr/dq/index modules for Phase 8 requirements.
- Online pipeline: ExecutionEngine with agents; no explicit `/api/ask` RAG online QA path, hybrid retrieval, verify gate, or decision output.
- HITL queue: not present.
- Eval suites: Phase 7 docs exist; Phase 8 offline/online eval suites not present.

## Deploy/Release State
- Dockerfile and docker-compose.yml present but not validated in this phase.
- No release gate config (`configs/release_gate.yaml` missing).
- No promote/rollback scripts for index pointers.

## Gaps vs Phase 8 Targets
- Missing unified `make setup/test/build/run/eval/deploy`.
- Missing offline pipeline (ingestion → parse/OCR/table → DQ → chunk → embed → faiss index → offline gate).
- Missing online pipeline (query understanding/routing, retrieval, rerank policy hook, generation with citations, verify, decision).
- Missing HITL queue + scripts.
- Missing eval suites (offline_eval_suite.json / online_eval_suite.json) and evidence pack export.
- Missing canary/rollback index pointer scripts and audit log.
- Missing docs: phase8_change_log.md, phase8_production_rag_spec.md.

## Immediate Risks
- Backend imports require PYTHONPATH; need standardized run wrapper/Makefile.
- No RAG QA API path; integration with frontend workbenches not defined.
- Deployment not validated; compose may fail without new services/volumes.



