from backend.eval.use_case_runner import evaluate_use_cases


def test_use_case_eval_pass(tmp_path, monkeypatch):
    # Use real use_case definitions in eval/use_cases
    from shutil import copytree
    from pathlib import Path

    src = Path("eval/use_cases")
    dst = Path(tmp_path) / "eval" / "use_cases"
    dst.parent.mkdir(parents=True, exist_ok=True)
    copytree(src, dst)

    monkeypatch.chdir(tmp_path)

    answer_bundle = {
        "annual_fee": {
            "fields": {"fee": 0.0, "condition": "刷卡3次免年费"},
            "citations": [{"chunk_id": "c1"}],
        },
        "cashback": {
            "fields": {"rate": 0.05, "category": "超市"},
            "citations": [{"chunk_id": "c2"}],
        },
        "terms_conflict": {
            "fields": {"conflict_detected": True},
            "citations": [{"chunk_id": "c3"}],
        },
    }

    results = evaluate_use_cases(answer_bundle)
    assert results["annual_fee"] == "pass"
    assert results["cashback"] == "pass"
    assert results["terms_conflict"] == "pass"


def test_use_case_eval_fail_missing_field_or_citation(tmp_path, monkeypatch):
    from shutil import copytree
    from pathlib import Path

    src = Path("eval/use_cases")
    dst = Path(tmp_path) / "eval" / "use_cases"
    dst.parent.mkdir(parents=True, exist_ok=True)
    copytree(src, dst)

    monkeypatch.chdir(tmp_path)

    answer_bundle = {
        "annual_fee": {
            # missing "condition"
            "fields": {"fee": 0.0},
            "citations": [{"chunk_id": "c1"}],
        },
        "cashback": {
            "fields": {"rate": 0.10, "category": "超市"},
            # missing citations
            "citations": [],
        },
        "terms_conflict": {
            "fields": {},
            "citations": [{"chunk_id": "c3"}],
        },
    }

    results = evaluate_use_cases(answer_bundle)
    assert results["annual_fee"] == "fail"
    assert results["cashback"] == "fail"
    assert results["terms_conflict"] == "fail"




