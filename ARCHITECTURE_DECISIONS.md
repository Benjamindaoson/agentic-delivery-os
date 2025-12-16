# Gate Authority and Learning Consumption

## GateDecision as Single Source of Truth
- All deploy actions (promote, rollback, block) are executed only by reading `gate_decision.json` through `backend/governance/gate_executor.py`.
- The executor fails fast with a `NoAuthoritativeGateDecision` error if the artifact is missing or malformed, preventing any inference from eval or learning outputs.
- Use-case flows now focus on producing artifacts; action selection is fully deferred to the gate executor, ensuring replayability and auditability.

## Mandatory LearningSignal Consumption
- Each run emits a structured `LearningSignal` with `signal_id`, severity, recommended action, and `consumed` state persisted to `learning_signal.jsonl`.
- `load_pending_learning_signals` injects any unconsumed signals into gate evaluation; severity `MED`+ forces a `blocked` gate decision with reason `"Unconsumed learning signal"`.
- Signals can only be cleared via explicit consumption (e.g., data repair, rollback, or HITL closure), guaranteeing that learning feedback always influences subsequent gates.
