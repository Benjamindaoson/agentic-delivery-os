# Data Intelligence Agent Specification (v1.0)

## Scope
- Deterministic, auditable Data Intelligence Agent for RAG ingestion.
- Supports unattended/batch/SaaS/API; no blocking waits.

## Modules (runtime/data_intel/)
- `type_classifier.py`  
  Input: `input_files[]` (path/url, mime, size)  
  Output per file: `{type_tags[], need_ocr, need_table_recovery, length_class}`
- `strategy_enumerator.py`  
  Enumerates candidate strategies per file (id, pipeline_steps, cost_estimate, accuracy_band, latency_class, risks). OCR options: MinerU / DeepSeek OCR / PaddleOCR.
- `tradeoff_analyzer.py`  
  Detects trade-offs (cost_accuracy, speed_quality, completeness); labels RESOLVABLE / NON_RESOLVABLE.
- `policy_resolver.py`  
  Applies tenant_policy, tenant_context, system_constraints. Rules: authorized→AUTO_RESOLVED; exceed→POLICY_VIOLATION; no policy→UNAUTHORIZED_TRADEOFF; unattended→no waiting, choose conservative legal strategy or fail with evidence.
- `executor.py`  
  Orchestrates classify → enumerate → analyze → resolve; stores evidence.

## Storage & Evidence
- Path: `artifacts/data_intel/{run_id}/`
- Files:
  - `input_snapshot.json`
  - `tenant_policy.json`
  - `strategy_plan.json`
  - `tradeoffs.json`
  - `resolutions.json`
  - `evidence.json`
- Hashes (in evidence): `input_snapshot_hash`, `policy_hash`, `strategy_plan_hash`, `decision_hash`, `run_id`
- Replay: use stored inputs + policy + strategy_plan.

## API (read-only)
- `POST /api/data-intel/run`  
  Body: `{input_files, tenant_context, tenant_policy?, system_constraints?, runtime_capabilities?}`  
  Resp: `{run_id}`
- `GET /api/data-intel/run/{run_id}/result`  
  Resp: `evidence` (structured, no narrative)

## Failure Semantics
- AUTHORIZATION_FAILURE
- COST_LIMIT_EXCEEDED
- DATA_UNPROCESSABLE
- TOOL_UNAVAILABLE

## Testing
- Unit tests cover policy resolution: authorized / violation / unattended (see `tests/test_data_intel_policy.py`).
