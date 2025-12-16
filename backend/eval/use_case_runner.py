from __future__ import annotations

import json
import os
from typing import Any, Dict, List


USE_CASE_DIR = os.path.join("eval", "use_cases")


def _load_use_case_defs() -> Dict[str, Dict[str, Any]]:
    scenarios: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(USE_CASE_DIR):
        return scenarios
    for name in os.listdir(USE_CASE_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(USE_CASE_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        scenario = data.get("scenario") or os.path.splitext(name)[0]
        scenarios[scenario] = data
    return scenarios


def evaluate_use_cases(answer_bundle: Dict[str, Any]) -> Dict[str, str]:
    """
    Evaluate use-cases based on structured answers.

    answer_bundle example:
    {
      "annual_fee": {
        "fields": {"fee": 0, "condition": "首年刷卡3次免年费"},
        "citations": [{"chunk_id": "c1"}]
      },
      ...
    }

    Returns:
      {"annual_fee": "pass" | "fail", ...}
    """
    use_cases = _load_use_case_defs()
    results: Dict[str, str] = {}

    for scenario, definition in use_cases.items():
        expected_fields: List[str] = definition.get("expected_fields", [])
        rules: Dict[str, str] = definition.get("evaluation_rules", {})
        ans = answer_bundle.get(scenario) or {}
        fields = ans.get("fields") or {}
        citations = ans.get("citations") or []

        ok = True

        # Field existence
        for field in expected_fields:
            if rules.get(field) == "must_exist" and field not in fields:
                ok = False

        # Numeric exact / tolerance
        for field, rule in rules.items():
            if rule == "numeric_exact_or_tolerance" and field in fields:
                expected = definition.get("expected_values", {}).get(field)
                actual = fields.get(field)
                if expected is not None and isinstance(actual, (int, float)):
                    # simple tolerance: 1% of expected or 0.01 whichever larger
                    tol = max(abs(expected) * 0.01, 0.01)
                    if abs(actual - expected) > tol:
                        ok = False

        # Citation requirement
        if rules.get("citation") == "required" and not citations:
            ok = False

        results[scenario] = "pass" if ok else "fail"

    return results





