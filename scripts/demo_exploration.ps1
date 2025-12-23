# Demo script: trigger a single exploration run (shadow-only)
Set-Location (Join-Path $PSScriptRoot "..")

$env:PYTHONPATH = "."

python - <<'PY'
import asyncio
from runtime.exploration.exploration_engine import ExplorationEngine

async def main():
    engine = ExplorationEngine()
    decision = await engine.maybe_explore(
        run_id="demo_run",
        run_signals={
            "run_success": False,
            "pattern_is_new": True,
            "retrieval_policy_id": "basic_v1",
            "generation_template_id": "rag_answer:v1",
        },
        attribution={"primary_cause": "RETRIEVAL_MISS"},
        policy_kpis={"success_rate": 0.6},
    )
    print("Decision artifact:", "artifacts/exploration/decisions/demo_run.json")
    print("Budget artifact:", "artifacts/exploration/budget_state.json")
    print("Candidate artifacts dir:", "artifacts/policy/candidates/")
    print("Shadow diff dir:", "artifacts/eval/shadow_diff/")
    print("Regression report:", "artifacts/policy_regression_report.json")
    print("Decision summary:", decision)

asyncio.run(main())
PY



