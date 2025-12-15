"""
Semantic Asset Elevation (post-worker semantic mapping).
Workers do not perform semantics; this layer maps to roles.
"""
from typing import Dict, Any, List


def elevate(structured: Dict[str, Any], chunks: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map chunks/tables/sections into semantic roles deterministically.
    Placeholder deterministic mapping: based on presence of 'table' or 'section'.
    """
    semantic_roles: List[Dict[str, Any]] = []
    for ch in chunks.get("chunks", []):
        role = "faq" if "?" in ch.get("content", "") else "clause"
        semantic_roles.append(
            {
                "chunk_id": ch.get("chunk_id"),
                "role": role,
                "source_ref": ch.get("source_ref"),
            }
        )
    return {"semantic_roles": semantic_roles}


