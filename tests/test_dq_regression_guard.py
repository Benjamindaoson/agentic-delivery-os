from backend.offline.dq_regression_guard import check_dq_regression


def test_dq_regression_no_previous():
    current = {
        "metrics": {
            "ocr_coverage": 0.8,
            "table_recovery_f1": 0.85,
            "empty_page_ratio": 0.1,
            "duplicate_page_ratio": 0.05,
        }
    }
    result = check_dq_regression(current_dq=current, previous_dq=None)
    assert result["regression_detected"] is False
    assert result["failed_metrics"] == []


def test_dq_regression_detects_worse_metrics():
    previous = {
        "metrics": {
            "ocr_coverage": 0.9,
            "table_recovery_f1": 0.9,
            "empty_page_ratio": 0.1,
            "duplicate_page_ratio": 0.05,
        }
    }
    current = {
        "metrics": {
            "ocr_coverage": 0.8,          # worse (should regress)
            "table_recovery_f1": 0.85,    # worse (should regress)
            "empty_page_ratio": 0.2,      # worse (higher)
            "duplicate_page_ratio": 0.1,  # worse (higher)
        }
    }
    result = check_dq_regression(current_dq=current, previous_dq=previous)
    assert result["regression_detected"] is True
    # All four metrics should be flagged
    for m in [
        "ocr_coverage",
        "table_recovery_f1",
        "empty_page_ratio",
        "duplicate_page_ratio",
    ]:
        assert m in result["failed_metrics"]




