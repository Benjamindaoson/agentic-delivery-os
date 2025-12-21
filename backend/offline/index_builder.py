"""
Typed / Multi-Vector Index Strategy (Phase 8 · P4-3)

This module defines how different chunk types map to index strategies.
It does NOT yet wire into the main offline pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, List

from runtime.index.index_manifest import build_index_manifest


CHUNK_TYPE_STRATEGY: Dict[str, List[str]] = {
    "numeric_table": ["value_store", "vector"],
    "clause": ["dense", "sparse"],
    "faq": ["dense"],
    "timeline": ["sparse", "metadata"],
}


def build_index_with_strategies(
    chunks: List[Dict[str, Any]],
    chunk_strategy: str,
    embedding_model: str,
    bm25: bool,
) -> Dict[str, Any]:
    """
    Build an index manifest that includes an index_strategy_map based on
    the chunk_type of provided chunks.

    The mapping is hard-coded:
      - numeric_table → value_store + vector
      - clause       → dense + sparse
      - faq          → dense
      - timeline     → sparse + metadata
    """
    strategy_map: Dict[str, Dict[str, Any]] = {}
    for ch in chunks:
        ctype = ch.get("chunk_type")
        if ctype not in CHUNK_TYPE_STRATEGY:
            continue
        if ctype not in strategy_map:
            strategy_map[ctype] = {"modes": CHUNK_TYPE_STRATEGY[ctype]}

    manifest = build_index_manifest(chunk_strategy, embedding_model, bm25)
    manifest["index_strategy_map"] = strategy_map
    return manifest

























