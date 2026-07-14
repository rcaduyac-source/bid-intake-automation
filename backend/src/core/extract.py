from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from docx import Document
from PIL import Image

ALLOWED_EXT = {".pdf", ".docx", ".txt"}
OCR_MIN_CHARS = 40


def is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def extract_file(path: str | Path, filename: str | None = None) -> tuple[str, list[dict]]:
    """Return (full_text, pages[{source, page, text}])."""
    path = Path(path)
    name = filename or path.name
    ext = Path(name).suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(path, name)
    if ext == ".docx":
        return _extract_docx(path, name)
    if ext == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        return text, [{"source": name, "page": 1, "text": text}]
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(path: Path, name: str) -> tuple[str, list[dict]]:
    doc = fitz.open(path)
    pages: list[dict] = []
    parts: list[str] = []
    try:
        for i, page in enumerate(doc, start=1):
            text = (page.get_text("text") or "").strip()
            if len(text) < OCR_MIN_CHARS:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr = pytesseract.image_to_string(img) or ""
                text = ocr.strip() or text
            pages.append({"source": name, "page": i, "text": text})
            if text:
                parts.append(text)
    finally:
        doc.close()
    return "\n\n".join(parts), pages


def _extract_docx(path: Path, name: str) -> tuple[str, list[dict]]:
    document = Document(path)
    paras = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]
    text = "\n".join(paras)
    return text, [{"source": name, "page": 1, "text": text}]


def chunk_pages(pages: list[dict], max_chars: int = 1800) -> list[dict]:
    """Split page texts into overlapping-ish chunks for embedding."""
    chunks: list[dict] = []
    seq = 0
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        if len(text) <= max_chars:
            seq += 1
            chunks.append(
                {
                    "seq": seq,
                    "source": page["source"],
                    "page": page["page"],
                    "text": text,
                }
            )
            continue
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            piece = text[start:end].strip()
            if piece:
                seq += 1
                chunks.append(
                    {
                        "seq": seq,
                        "source": page["source"],
                        "page": page["page"],
                        "text": piece,
                    }
                )
            if end >= len(text):
                break
            start = end - 200
    return chunks
