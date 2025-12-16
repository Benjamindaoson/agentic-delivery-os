from backend.offline.index_builder import build_index_with_strategies


def test_index_strategy_map_per_chunk_type():
    chunks = [
        {"chunk_type": "numeric_table"},
        {"chunk_type": "clause"},
        {"chunk_type": "faq"},
        {"chunk_type": "timeline"},
    ]
    manifest = build_index_with_strategies(
        chunks=chunks,
        chunk_strategy="v1",
        embedding_model="multi-vec",
        bm25=True,
    )
    strategy_map = manifest.get("index_strategy_map", {})

    assert strategy_map["numeric_table"]["modes"] == ["value_store", "vector"]
    assert strategy_map["clause"]["modes"] == ["dense", "sparse"]
    assert strategy_map["faq"]["modes"] == ["dense"]
    assert strategy_map["timeline"]["modes"] == ["sparse", "metadata"]


def test_numeric_table_not_dense_only():
    chunks = [{"chunk_type": "numeric_table"}]
    manifest = build_index_with_strategies(
        chunks=chunks,
        chunk_strategy="v1",
        embedding_model="multi-vec",
        bm25=False,
    )
    modes = manifest["index_strategy_map"]["numeric_table"]["modes"]
    # Ensure numeric_table is not incorrectly configured as dense-only
    assert "dense" not in modes
    assert "value_store" in modes and "vector" in modes




