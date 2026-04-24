"""Extract plain text from PDF, DOCX, and text files.

Page boundaries are preserved as structured markers so downstream tools
(and Claude) can always reference back to the original page number.
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".rst"}

PAGE_MARKER = "─── [第 {n} 页] " + "─" * 40


def extract_text(path: str | Path) -> str:
    """
    Extract plain text from a document.
    PDF page boundaries are preserved as  ─── [第 N 页] ─── markers.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext in (".docx", ".doc"):
        return _extract_docx(path)
    elif ext in (".txt", ".md", ".rst"):
        return path.read_text(errors="replace")
    else:
        raise ValueError(
            f"不支持的格式: {ext}。支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("请安装 pypdf: pip install pypdf")

    reader = PdfReader(str(path))
    pages: list[str] = []

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        marker = PAGE_MARKER.format(n=i)
        pages.append(f"{marker}\n\n{text.strip()}")

    return "\n\n".join(pages)


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
        from docx.oxml.ns import qn
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")

    doc = Document(str(path))
    output: list[str] = []
    page = 1
    output.append(PAGE_MARKER.format(n=page))

    for para in doc.paragraphs:
        # Detect manual page breaks
        for br in para._element.iter(qn("w:lastRenderedPageBreak")):
            page += 1
            output.append(f"\n\n{PAGE_MARKER.format(n=page)}\n")
            break

        text = para.text.strip()
        if text:
            output.append(text)

    return "\n\n".join(output)
