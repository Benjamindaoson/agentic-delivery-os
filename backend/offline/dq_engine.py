"""
DQ Engine for Offline Pipeline (Phase 8 P0)

Responsibilities:
- Compute document-level data quality metrics from a ParsedDoc-like structure
- Produce a structured, auditable dq_report dict that can be written to disk
- Apply configurable thresholds (from YAML) to decide PASS / WARN / FAIL
- Drive downstream behaviour: PASS → continue, WARN → HITL, FAIL → block index

The engine is deterministic and does not rely on ML models.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class DQConfig:
    ocr_coverage_warn: float = 0.6
    ocr_coverage_fail: float = 0.3
    table_recovery_warn: float = 0.7
    table_recovery_fail: float = 0.4
    empty_page_ratio_warn: float = 0.5
    empty_page_ratio_fail: float = 0.8
    duplicate_page_ratio_warn: float = 0.3
    duplicate_page_ratio_fail: float = 0.6


@dataclass
class DQMetrics:
    ocr_coverage: float
    table_recovery_rate: float
    empty_page_ratio: float
    duplicate_page_ratio: float
    language: str


@dataclass
class DQDecision:
    level: str  # PASS | WARN | FAIL
    reasons: List[str]


def _load_config(config_path: Optional[str] = None) -> DQConfig:
    """
    Load DQ thresholds from YAML. If the file is missing or invalid,
    fall back to safe defaults (no implicit weakening of gates).
    """
    path = config_path or os.path.join("configs", "dq_config.yaml")
    if not os.path.exists(path):
        return DQConfig()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = data.get("dq", {})
    return DQConfig(
        ocr_coverage_warn=float(cfg.get("ocr_coverage_warn", 0.6)),
        ocr_coverage_fail=float(cfg.get("ocr_coverage_fail", 0.3)),
        table_recovery_warn=float(cfg.get("table_recovery_warn", 0.7)),
        table_recovery_fail=float(cfg.get("table_recovery_fail", 0.4)),
        empty_page_ratio_warn=float(cfg.get("empty_page_ratio_warn", 0.5)),
        empty_page_ratio_fail=float(cfg.get("empty_page_ratio_fail", 0.8)),
        duplicate_page_ratio_warn=float(cfg.get("duplicate_page_ratio_warn", 0.3)),
        duplicate_page_ratio_fail=float(cfg.get("duplicate_page_ratio_fail", 0.6)),
    )


def _safe_div(n: float, d: float) -> float:
    return 0.0 if d == 0 else n / d


def _extract_pages(parsed_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    ParsedDoc is loosely defined; we support both:
    - explicit "pages": [{page_number, text, tables, ...}]
    - or we fallback to a single synthetic page from top-level fields.
    """
    pages = parsed_doc.get("pages")
    if isinstance(pages, list) and pages:
        return pages
    # Fallback: synthesize a single page from structured_blocks / tables
    blocks = parsed_doc.get("structured_blocks") or []
    tables = parsed_doc.get("tables") or []
    text = "\n".join(str(b.get("text", "")) for b in blocks)
    return [
        {
            "page_number": 1,
            "text": text,
            "tables": tables,
        }
    ]


def _compute_ocr_coverage(parsed_doc: Dict[str, Any]) -> float:
    """
    Heuristic OCR coverage:
    - If OCR text blocks present: treat as fully covered
    - Otherwise, 0.0
    For production, this can be extended with true char-level stats from OCR.
    """
    ocr = parsed_doc.get("ocr_output") or {}
    blocks = ocr.get("ocr_text_blocks") or parsed_doc.get("ocr_text_blocks") or []
    if not isinstance(blocks, list):
        return 0.0
    return 1.0 if len(blocks) > 0 else 0.0


def _compute_table_recovery_rate(parsed_doc: Dict[str, Any]) -> float:
    tables = parsed_doc.get("tables") or []
    if not isinstance(tables, list) or not tables:
        return 0.0
    total = len(tables)
    recovered = 0
    for t in tables:
        cells = t.get("cells") or t.get("rows")
        if cells:
            recovered += 1
    return _safe_div(recovered, total)


def _compute_empty_and_duplicate_ratios(parsed_doc: Dict[str, Any]) -> Tuple[float, float]:
    pages = _extract_pages(parsed_doc)
    if not pages:
        return 1.0, 0.0
    total = len(pages)
    empty = 0
    seen_hashes: Dict[str, int] = {}
    for p in pages:
        text = str(p.get("text", "") or "").strip()
        tables = p.get("tables") or []
        if not text and not tables:
            empty += 1
        key = f"{text}\nT:{len(tables)}"
        seen_hashes[key] = seen_hashes.get(key, 0) + 1
    dup_count = sum(c - 1 for c in seen_hashes.values() if c > 1)
    return _safe_div(empty, total), _safe_div(dup_count, total)


def _detect_language(parsed_doc: Dict[str, Any]) -> str:
    """
    Very cheap language detection based on character ranges.
    This is deterministic and sufficient for zh/en/mixed/unknown buckets.
    """
    pages = _extract_pages(parsed_doc)
    text = "".join(str(p.get("text", "")) for p in pages)
    if not text:
        return "unknown"
    zh = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    en = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    total = zh + en
    if total == 0:
        return "unknown"
    zh_ratio = zh / total
    en_ratio = en / total
    if zh_ratio > 0.8:
        return "zh"
    if en_ratio > 0.8:
        return "en"
    return "mixed"


def compute_metrics(parsed_doc: Dict[str, Any]) -> DQMetrics:
    ocr_cov = _compute_ocr_coverage(parsed_doc)
    table_rate = _compute_table_recovery_rate(parsed_doc)
    empty_ratio, dup_ratio = _compute_empty_and_duplicate_ratios(parsed_doc)
    lang = _detect_language(parsed_doc)
    # clamp to [0,1]
    return DQMetrics(
        ocr_coverage=max(0.0, min(1.0, ocr_cov)),
        table_recovery_rate=max(0.0, min(1.0, table_rate)),
        empty_page_ratio=max(0.0, min(1.0, empty_ratio)),
        duplicate_page_ratio=max(0.0, min(1.0, dup_ratio)),
        language=lang,
    )


def decide_dq(metrics: DQMetrics, cfg: Optional[DQConfig] = None) -> DQDecision:
    cfg = cfg or DQConfig()
    reasons: List[str] = []
    level = "PASS"

    def update_level(new_level: str, reason: str) -> None:
        nonlocal level
        reasons.append(reason)
        order = {"PASS": 0, "WARN": 1, "FAIL": 2}
        if order[new_level] > order[level]:
            level = new_level

    # OCR coverage
    if metrics.ocr_coverage < cfg.ocr_coverage_fail:
        update_level("FAIL", "ocr_coverage_below_fail_threshold")
    elif metrics.ocr_coverage < cfg.ocr_coverage_warn:
        update_level("WARN", "ocr_coverage_below_warn_threshold")

    # Table recovery
    if metrics.table_recovery_rate < cfg.table_recovery_fail:
        update_level("FAIL", "table_recovery_below_fail_threshold")
    elif metrics.table_recovery_rate < cfg.table_recovery_warn:
        update_level("WARN", "table_recovery_below_warn_threshold")

    # Empty pages
    if metrics.empty_page_ratio > cfg.empty_page_ratio_fail:
        update_level("FAIL", "empty_page_ratio_above_fail_threshold")
    elif metrics.empty_page_ratio > cfg.empty_page_ratio_warn:
        update_level("WARN", "empty_page_ratio_above_warn_threshold")

    # Duplicate pages
    if metrics.duplicate_page_ratio > cfg.duplicate_page_ratio_fail:
        update_level("FAIL", "duplicate_page_ratio_above_fail_threshold")
    elif metrics.duplicate_page_ratio > cfg.duplicate_page_ratio_warn:
        update_level("WARN", "duplicate_page_ratio_above_warn_threshold")

    return DQDecision(level=level, reasons=reasons)


def build_dq_report(
    parsed_doc: Dict[str, Any],
    config_path: Optional[str] = None,
    doc_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute metrics + decision and build a dq_report dict that matches
    `schemas/dq_report.schema.json`.
    """
    cfg = _load_config(config_path)
    metrics = compute_metrics(parsed_doc)
    decision = decide_dq(metrics, cfg)
    report: Dict[str, Any] = {
        "doc_id": doc_id or parsed_doc.get("doc_id"),
        "run_id": run_id,
        "metrics": asdict(metrics),
        "decision": {
            "level": decision.level,
            "reasons": decision.reasons,
        },
        "config_snapshot": asdict(cfg),
    }
    return report


def persist_dq_report(
    report: Dict[str, Any],
    base_dir: Optional[str] = None,
) -> str:
    """
    Persist dq_report.json to disk under artifacts/offline/{doc_id}/{run_id}/
    (or compatible base_dir). Returns the file path.
    """
    doc_id = report.get("doc_id") or "unknown_doc"
    run_id = report.get("run_id") or "unknown_run"
    root = base_dir or os.path.join("artifacts", "offline", doc_id, str(run_id))
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "dq_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return path
































