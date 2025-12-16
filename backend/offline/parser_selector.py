"""
Parser Strategy Selector (Phase 8 P0)

Responsibility:
- Inspect basic document signals (mime, size, simple text stats, table hints)
- Decide doc_type: digital_pdf | scanned_pdf | table_heavy
- Emit an explicit, auditable strategy declaration:
  {
    "doc_type": "...",
    "strategy": ["text" | "ocr" | "layout" | "table", ...],
    "confidence": 0.0–1.0
  }

This is a deterministic rule engine, not if/else sprinkled inline in workers.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class ParserDecision:
  doc_type: str
  strategy: List[str]
  confidence: float

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


def select_parser_strategy(doc_meta: Dict[str, Any]) -> ParserDecision:
  """
  Inputs (doc_meta is intentionally simple and stable):
  {
    "mime": "...",
    "has_ocr": bool,
    "has_tables": bool,
    "page_count": int,
    "text_density": float  (0~1, approx chars/page),
  }
  """
  mime = (doc_meta.get("mime") or "").lower()
  has_ocr = bool(doc_meta.get("has_ocr"))
  has_tables = bool(doc_meta.get("has_tables"))
  page_count = int(doc_meta.get("page_count") or 0)
  text_density = float(doc_meta.get("text_density") or 0.0)

  # Default baseline
  decision = ParserDecision(doc_type="digital_pdf", strategy=["text"], confidence=0.5)

  # Table-heavy signal
  if has_tables and page_count > 0:
    decision.doc_type = "table_heavy"
    decision.strategy = ["text", "table"]
    decision.confidence = 0.8
    return decision

  # Scanned PDF signal:
  # - mime is PDF
  # - no existing OCR text
  # - low text density
  if "pdf" in mime and (not has_ocr) and text_density < 0.2:
    decision.doc_type = "scanned_pdf"
    decision.strategy = ["ocr", "layout", "table"]
    decision.confidence = 0.9
    return decision

  # Digital PDF: mime is PDF and density reasonable
  if "pdf" in mime and text_density >= 0.2:
    decision.doc_type = "digital_pdf"
    decision.strategy = ["text", "layout", "table"] if has_tables else ["text", "layout"]
    decision.confidence = 0.9
    return decision

  # Fallback: non-PDF (e.g. docx/html) → text-first with moderate confidence
  decision.doc_type = "digital_pdf" if "pdf" in mime else "digital_pdf"
  decision.strategy = ["text"]
  decision.confidence = 0.5
  return decision





