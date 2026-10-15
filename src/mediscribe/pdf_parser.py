"""Extract text from uploaded PDF, TXT, or raw text input."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Result of parsing an uploaded document."""
    raw_text: str
    page_count: int = 1
    source_type: str = "text"  # "pdf", "txt", "text"
    metadata: dict = field(default_factory=dict)


def extract_text_from_pdf(file_bytes: bytes) -> ParsedDocument:
    """Extract text from a PDF using pdfplumber (preferred) or PyPDF2 fallback."""
    text = ""
    page_count = 0

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except ImportError:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except ImportError:
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(io.BytesIO(file_bytes))
                page_count = len(reader.pages)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            except ImportError:
                raise RuntimeError(
                    "No PDF parser available. Install pdfplumber, pypdf, or PyPDF2: "
                    "pip install pdfplumber"
                )

    if not text.strip():
        raise ValueError("Could not extract any text from the uploaded PDF.")

    return ParsedDocument(
        raw_text=text.strip(),
        page_count=page_count,
        source_type="pdf",
        metadata={"byte_size": len(file_bytes)},
    )


def extract_text_from_txt(file_bytes: bytes) -> ParsedDocument:
    """Extract text from a plain-text file."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = file_bytes.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError("Unable to decode the text file with any supported encoding.")

    if not text.strip():
        raise ValueError("The uploaded text file is empty.")

    return ParsedDocument(
        raw_text=text.strip(),
        source_type="txt",
        metadata={"byte_size": len(file_bytes), "encoding": encoding},
    )


def segment_into_turns(text: str) -> list[dict]:
    """Segment raw text into pseudo-transcript turns.

    Heuristic:
    - Lines starting with known speaker labels ("Doctor:", "Patient:", etc.) become labelled turns.
    - Otherwise, split by paragraphs and alternate between patient/clinician guesses.
    """
    speaker_pattern = re.compile(
        r"^(?P<speaker>doctor|dr|clinician|physician|patient|pt)\s*[:\-–]\s*",
        re.IGNORECASE | re.MULTILINE,
    )

    labelled = list(speaker_pattern.finditer(text))
    turns: list[dict] = []

    if labelled:
        for idx, match in enumerate(labelled):
            start = match.end()
            end = labelled[idx + 1].start() if idx + 1 < len(labelled) else len(text)
            speaker_raw = match.group("speaker").lower()
            speaker = "clinician" if speaker_raw in ("doctor", "dr", "clinician", "physician") else "patient"
            chunk = text[start:end].strip()
            if chunk:
                turns.append({
                    "turn_id": f"t{idx + 1}",
                    "speaker": speaker,
                    "text": chunk,
                })
    else:
        # Fallback: split by paragraphs/double-newlines
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            paragraphs = [s.strip() for s in text.split("\n") if s.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        for idx, para in enumerate(paragraphs):
            turns.append({
                "turn_id": f"t{idx + 1}",
                "speaker": "unknown",
                "text": para,
            })

    return turns
