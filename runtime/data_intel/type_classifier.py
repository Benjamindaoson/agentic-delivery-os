"""
Type classifier for Data Intelligence Agent.
Deterministic, heuristic-based classification without OCR execution.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List
import os


class LengthClass:
    SHORT = "SHORT"
    LONG = "LONG"
    VERY_LONG = "VERY_LONG"


class TypeTag:
    TEXT_NATIVE = "TEXT_NATIVE"
    IMAGE_DOMINANT = "IMAGE_DOMINANT"
    TABLE_STRUCTURED = "TABLE_STRUCTURED"
    SEMI_STRUCTURED = "SEMI_STRUCTURED"
    MIXED_HETEROGENEOUS = "MIXED_HETEROGENEOUS"


@dataclass
class FileClassification:
    type_tags: List[str]
    need_ocr: bool
    need_table_recovery: bool
    table_type: str
    length_class: str
    file_path: str
    mime_type: str
    size_bytes: int
    cheap_signals: Dict[str, float]
    sampling_applied: bool
    sample_manifest: List[Dict[str, str]]


EXT_TO_TAG = {
    # text native
    ".txt": [TypeTag.TEXT_NATIVE],
    ".md": [TypeTag.TEXT_NATIVE],
    ".pdf": [TypeTag.TEXT_NATIVE],
    ".doc": [TypeTag.TEXT_NATIVE],
    ".docx": [TypeTag.TEXT_NATIVE],
    ".html": [TypeTag.SEMI_STRUCTURED],
    ".htm": [TypeTag.SEMI_STRUCTURED],
    ".json": [TypeTag.SEMI_STRUCTURED],
    # tables
    ".csv": [TypeTag.TABLE_STRUCTURED],
    ".tsv": [TypeTag.TABLE_STRUCTURED],
    ".xls": [TypeTag.TABLE_STRUCTURED],
    ".xlsx": [TypeTag.TABLE_STRUCTURED],
    # images
    ".png": [TypeTag.IMAGE_DOMINANT],
    ".jpg": [TypeTag.IMAGE_DOMINANT],
    ".jpeg": [TypeTag.IMAGE_DOMINANT],
    ".tif": [TypeTag.IMAGE_DOMINANT],
    ".tiff": [TypeTag.IMAGE_DOMINANT],
}


def _length_class(size_bytes: int) -> str:
    if size_bytes <= 200_000:
        return LengthClass.SHORT
    if size_bytes <= 2_000_000:
        return LengthClass.LONG
    return LengthClass.VERY_LONG


def _cheap_signals(size_bytes: int, mime: str) -> Dict[str, float]:
    """
    Produce cheap signals (no OCR/LLM). Values are heuristic placeholders.
    """
    # text_coverage_ratio: rough heuristic from mime
    text_cov = 0.8 if "text" in mime or "pdf" in mime else 0.2 if "image" in mime else 0.5
    image_density = 0.7 if "image" in mime else 0.3 if "pdf" in mime else 0.1
    table_boundary = 0.6 if "spreadsheet" in mime or "excel" in mime or "csv" in mime else 0.2
    encoding_entropy = 0.5
    embedded_font = 1.0 if "pdf" in mime else 0.0
    return {
        "text_coverage_ratio": round(text_cov, 2),
        "image_density": round(image_density, 2),
        "table_boundary_heuristic": round(table_boundary, 2),
        "encoding_entropy": round(encoding_entropy, 2),
        "embedded_font_existence": embedded_font,
    }


def _sampling_needed(size_bytes: int, mime: str, path: str) -> bool:
    # Conditions per prompt
    large_pdf = ("pdf" in mime) and size_bytes > 0 and size_bytes > 0  # placeholder, pdf pages unknown
    return size_bytes > 20_000_000 or large_pdf


def _sample_manifest() -> List[Dict[str, str]]:
    return [
        {"segment": "start", "method": "page_or_chunk", "ratio": "≤5%"},
        {"segment": "middle", "method": "page_or_chunk", "ratio": "≤5%"},
        {"segment": "end", "method": "page_or_chunk", "ratio": "≤5%"},
        {"segment": "random", "method": "page_or_chunk", "ratio": "≤5%"},
    ]


def classify_file(file_info: Dict) -> Dict:
    """
    Classify a single file deterministically.
    file_info: {path/url, mime, size}
    """
    path = file_info.get("path") or file_info.get("url") or ""
    mime = (file_info.get("mime") or "").lower()
    size = int(file_info.get("size") or 0)
    ext = os.path.splitext(path)[1].lower()

    type_tags = EXT_TO_TAG.get(ext, [])

    # MIME heuristics
    if not type_tags:
        if mime.startswith("image/"):
            type_tags = [TypeTag.IMAGE_DOMINANT]
        elif "json" in mime:
            type_tags = [TypeTag.SEMI_STRUCTURED]
        elif "html" in mime:
            type_tags = [TypeTag.SEMI_STRUCTURED]
        elif "spreadsheet" in mime or "excel" in mime:
            type_tags = [TypeTag.TABLE_STRUCTURED]
        elif "csv" in mime:
            type_tags = [TypeTag.TABLE_STRUCTURED]
        elif "pdf" in mime:
            type_tags = [TypeTag.TEXT_NATIVE]
        else:
            type_tags = [TypeTag.MIXED_HETEROGENEOUS]

    # need_ocr heuristic: images or image-dominant PDFs (simplified)
    need_ocr = TypeTag.IMAGE_DOMINANT in type_tags
    if "pdf" in mime and need_ocr is False:
        need_ocr = False

    # need_table_recovery heuristic
    need_table_recovery = TypeTag.TABLE_STRUCTURED in type_tags and ext not in [
        ".csv",
        ".tsv",
    ]
    table_type = "NONE"
    if TypeTag.TABLE_STRUCTURED in type_tags:
        if need_ocr:
            table_type = "SCANNED"
        else:
            table_type = "NATIVE"
    elif TypeTag.MIXED_HETEROGENEOUS in type_tags:
        table_type = "LAYOUT"

    length_cls = _length_class(size)
    signals = _cheap_signals(size, mime)
    sampling = _sampling_needed(size, mime, path)
    sample_manifest = _sample_manifest() if sampling else []

    classification = FileClassification(
        type_tags=type_tags,
        need_ocr=need_ocr,
        need_table_recovery=need_table_recovery,
        table_type=table_type,
        length_class=length_cls,
        file_path=path,
        mime_type=mime,
        size_bytes=size,
        cheap_signals=signals,
        sampling_applied=sampling,
        sample_manifest=sample_manifest,
    )
    return asdict(classification)


def classify_inputs(input_files: List[Dict]) -> List[Dict]:
    """
    Classify a list of input files.
    """
    results = []
    for file_info in input_files:
        results.append(classify_file(file_info))
    return results
