import os

from backend.eval.continuous_eval_scheduler import (
    schedule_continuous_eval,
    EVAL_HISTORY_PATH,
)


def test_continuous_eval_sampling_selects_requests(tmp_path, monkeypatch):
    # Configure high sampling rate and max_daily_eval
    monkeypatch.chdir(tmp_path)
    os.makedirs("configs", exist_ok=True)
    with open("configs/continuous_eval.yaml", "w", encoding="utf-8") as f:
        f.write("sampling_rate: 0.5\nmax_daily_eval: 10\nshadow_mode: true\n")

    request_ids = [f"req_{i}" for i in range(100)]
    selected = schedule_continuous_eval(request_ids)

    # At least one request should be scheduled for eval
    assert len(selected) > 0
    assert len(selected) <= 10
    assert os.path.exists(EVAL_HISTORY_PATH)


def test_continuous_eval_disabled_when_sampling_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("configs", exist_ok=True)
    with open("configs/continuous_eval.yaml", "w", encoding="utf-8") as f:
        f.write("sampling_rate: 0.0\nmax_daily_eval: 10\nshadow_mode: true\n")

    request_ids = [f"req_{i}" for i in range(50)]
    selected = schedule_continuous_eval(request_ids)

    # When sampling_rate=0, no request should be scheduled
    assert selected == []























