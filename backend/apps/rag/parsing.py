"""Step 2 of indexing: turn a file into plain text.

Headings are kept as Markdown `#` lines where the format has them (DOCX styles), so the
markdown-aware chunker can keep sections together.
"""

from io import BytesIO
from pathlib import PurePath


class ParseError(Exception):
    """The file can't be turned into text (corrupt, encrypted, scanned image…)."""


def parse(filename: str, data: bytes) -> str:
    ext = PurePath(filename).suffix.lower()
    if ext == ".pdf":
        text = _pdf(data)
    elif ext == ".docx":
        text = _docx(data)
    elif ext in {".md", ".markdown", ".txt"}:
        text = data.decode("utf-8", errors="replace")
    else:
        raise ParseError(f"Unsupported file type: {ext or 'none'}")

    text = text.replace("\r\n", "\n").replace("\x00", "").strip()
    if not text:
        raise ParseError("No text could be extracted (is it a scanned image?)")
    return text


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("The PDF is password-protected")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise ParseError(f"Couldn't read the PDF: {exc}") from exc
    # Blank line between pages so they never merge mid-sentence.
    return "\n\n".join(p.strip() for p in pages if p.strip())


def _docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - python-docx raises several unrelated types
        raise ParseError(f"Couldn't read the DOCX: {exc}") from exc
    lines = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = (p.style.name or "") if p.style else ""
        if style.startswith("Heading") and style[-1:].isdigit():
            lines.append(f"{'#' * int(style[-1])} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)
