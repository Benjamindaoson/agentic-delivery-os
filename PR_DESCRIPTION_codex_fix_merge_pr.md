Title: chore(repo): reorganize runtime state backends, add replay/llm/sandbox enhancements, CI golden-replay, seccomp profile and price table

Description:
This PR contains an engineering reorganization and a set of production-readiness improvements:

- Reorganized runtime state backends: moved Postgres implementation to `runtime/state/backends/`.
- Added deterministic replay runner and golden artifacts for CI (`runtime/replay/replay_runner.py`, `tests/golden/task_golden/*`).
- Implemented LLM runtime adapter with rate-limiting, retries, circuit breaker, cost accounting (`runtime/llm/adapter.py`) and Redis-based limiter (optional).
- Added Docker sandbox PoC with security options and image signing stub (`runtime/tools/tool_dispatcher.py`, `runtime/tools/image_signing.py`).
- Added sample seccomp profile (`security/seccomp_profiles/default.json`) and CI workflow to run tests + replay (`.github/workflows/golden-replay.yml`).
- Added price table config and integrated cost estimation into LLMAdapter (`configs/price_table.yaml`).
- Misc: tests moved/organized under `tests/`, docs/cleanup plans archived under `docs/`.

Validation:
- All unit/integration tests pass locally: `pytest` → 54 passed.
- Backend dependencies installed via `pip install -r backend/requirements.txt`.
- Replay and golden artifacts provided under `tests/golden/task_golden/` for CI guard.

Notes:
- CI workflow will run on push/PR to main/master; ensure repository settings allow Actions to run.
- To merge, either use the GitHub UI or run the command examples below (requires appropriate tokens/CLI).

Commands (choose one):

- Using GitHub CLI (preferred if installed):
  gh pr create --title "chore(repo): reorganize runtime state backends, add replay/llm/sandbox enhancements" --body-file PR_DESCRIPTION_codex_fix_merge_pr.md --base main --head codex/fix-merge-pr

- Using curl + GitHub API (requires GITHUB_TOKEN):
  curl -H "Authorization: token $GITHUB_TOKEN" -X POST "https://api.github.com/repos/Benjamindaoson/agentic-delivery-os/pulls" -d '{"title":"chore(repo): reorganize runtime state backends, add replay/llm/sandbox enhancements","head":"codex/fix-merge-pr","base":"main","body":"See PR_DESCRIPTION_codex_fix_merge_pr.md in the repo for details."}'

If you want me to create and merge the PR, provide a GitHub token with `repo` scope or grant me permission to run the PR creation. Otherwise, run one of the commands above or create the PR via GitHub UI (branch `codex/fix-merge-pr` is already pushed).


