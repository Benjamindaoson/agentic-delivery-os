"""
Format Router + Data Manifest
Deterministic routing; no OCR/LLM/cleaning.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import hashlib
import json
from datetime import datetime
import os

FILE_ROUTER = {
    "PDF_TEXT": "pdfplumber",
    "PDF_SCANNED": "ocr_pipeline",
    "DOCX": "python-docx",
    "HTML": "trafilatura",
    "XLSX": "openpyxl",
    "CSV": "openpyxl",
}

EXT_MAP = {
    ".pdf": "PDF_TEXT",
    ".docx": "DOCX",
    ".doc": "DOCX",
    ".html": "HTML",
    ".htm": "HTML",
    ".xlsx": "XLSX",
    ".xls": "XLSX",
    ".csv": "CSV",
}


@dataclass
class RoutedFile:
    file_id: str
    file_type: str
    router_path: str
    hash: str


def _hash_source(source: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def _file_hash(path: str, size: int, mime: str) -> str:
    return hashlib.sha256(f"{path}|{size}|{mime}".encode()).hexdigest()


def _file_type(mime: str, path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if "pdf" in mime:
        return "PDF_TEXT"
    if ext in EXT_MAP:
        return EXT_MAP[ext]
    if "html" in mime:
        return "HTML"
    if "csv" in mime:
        return "CSV"
    return "PDF_TEXT"


def route(source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input: {source_id, source_type, files:[{path,mime,size}]}
    Output: manifest deterministic.
    """
    files_out: List[RoutedFile] = []
    for f in source.get("files", []):
        ftype = _file_type(f.get("mime", ""), f.get("path", ""))
        router_path = FILE_ROUTER.get(ftype, "pdfplumber")
        fh = _file_hash(f.get("path", ""), f.get("size", 0), f.get("mime", ""))
        files_out.append(
            RoutedFile(
                file_id=fh[:16],
                file_type=ftype,
                router_path=router_path,
                hash=fh,
            )
        )

    manifest = {
        "files": [asdict(x) for x in files_out],
        "version": "v1",
        "created_at": datetime.now().isoformat(),
        "source_hash": _hash_source(source),
    }
    return {
        "corpus_id": f"corpus_{manifest['source_hash'][:12]}",
        "data_manifest": manifest,
    }


