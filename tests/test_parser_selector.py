from backend.offline.parser_selector import select_parser_strategy


def test_parser_selector_scanned_pdf():
    meta = {
        "mime": "application/pdf",
        "has_ocr": False,
        "has_tables": False,
        "page_count": 10,
        "text_density": 0.05,
    }
    decision = select_parser_strategy(meta)
    d = decision.to_dict()
    assert d["doc_type"] == "scanned_pdf"
    assert "ocr" in d["strategy"]
    assert d["confidence"] >= 0.8


def test_parser_selector_table_heavy():
    meta = {
        "mime": "application/pdf",
        "has_ocr": True,
        "has_tables": True,
        "page_count": 5,
        "text_density": 0.3,
    }
    decision = select_parser_strategy(meta)
    d = decision.to_dict()
    assert d["doc_type"] == "table_heavy"
    assert "table" in d["strategy"]
    assert d["confidence"] >= 0.7




