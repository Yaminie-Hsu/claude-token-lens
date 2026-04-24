"""Split a document into sections, each annotated with its page range.

Detects section headers by looking for common patterns in Chinese legal
documents and general structured documents:
  - Numbered clauses:   第一条  第八条  8.3  Article 5  Section II
  - Titled sections:    一、总则    二、定义
  - ALL-CAPS headings   (common in English contracts)
  - Markdown headings   # ## ###
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extractor import PAGE_MARKER
from ..estimator import count_tokens

# ── Section header patterns (ordered: most specific first) ───────────────────

_HEADER_PATTERNS = [
    # Chinese legal: 第一条 / 第8条 / 第十二条
    re.compile(r"^第[一二三四五六七八九十百千\d]+[条章节款项][\s　]"),
    # Chinese enumeration: 一、  二、  （一）
    re.compile(r"^[（(]?[一二三四五六七八九十]+[）)、．.]"),
    # Numeric: 1.  1.1  1.1.1  (with optional trailing text)
    re.compile(r"^\d+(\.\d+){0,3}[\s　、．.]"),
    # English: Article 5 / Section II / Chapter 3
    re.compile(r"^(Article|Section|Chapter|Part|Clause)\s+[\dIVXivx]+", re.IGNORECASE),
    # Markdown headings
    re.compile(r"^#{1,4}\s+\S"),
    # ALL CAPS line (min 4 chars, no page marker)
    re.compile(r"^[A-Z][A-Z\s\d]{3,}$"),
]

_PAGE_MARKER_RE = re.compile(r"^─+\s*\[第\s*(\d+)\s*页\]")


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Section:
    title: str
    content: str
    start_page: int
    end_page: int
    tokens: int = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = count_tokens(self.content)

    @property
    def page_ref(self) -> str:
        if self.start_page == self.end_page:
            return f"第 {self.start_page} 页"
        return f"第 {self.start_page}–{self.end_page} 页"

    def to_markdown(self) -> str:
        return (
            f"### {self.title}  ({self.page_ref}, ~{self.tokens} tokens)\n\n"
            f"{self.content.strip()}"
        )


@dataclass
class ChunkResult:
    sections: list[Section]
    total_pages: int

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.sections)

    def outline(self) -> str:
        """Return a compact table-of-contents string."""
        lines = ["## 文档目录\n", f"{'章节标题':<40} {'页码':<12} {'Tokens':>8}", "─" * 64]
        for s in self.sections:
            title = s.title[:38] + "…" if len(s.title) > 38 else s.title
            lines.append(f"{title:<40} {s.page_ref:<12} {s.tokens:>8,}")
        lines.append("─" * 64)
        lines.append(f"{'合计':<40} {'':12} {self.total_tokens:>8,}")
        return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def chunk_document(text: str) -> ChunkResult:
    """
    Split document text (with [第N页] markers) into labelled sections.
    """
    lines = text.splitlines()
    sections: list[Section] = []
    current_page = 1
    max_page = 1

    # Each entry: (line_index, title, page_at_start)
    header_positions: list[tuple[int, str, int]] = []
    page_at_line: dict[int, int] = {}   # line_index → current page at that point

    # First pass: record page changes and header positions
    running_page = 1
    for idx, line in enumerate(lines):
        m = _PAGE_MARKER_RE.match(line.strip())
        if m:
            running_page = int(m.group(1))
            max_page = max(max_page, running_page)
        page_at_line[idx] = running_page

        if _is_header(line):
            header_positions.append((idx, line.strip(), running_page))

    if not header_positions:
        # No detectable structure — return as a single section
        return ChunkResult(
            sections=[Section(
                title="（全文）",
                content=text,
                start_page=1,
                end_page=max_page,
            )],
            total_pages=max_page,
        )

    # Second pass: extract content between headers
    for i, (start_idx, title, start_page) in enumerate(header_positions):
        end_idx = header_positions[i + 1][0] if i + 1 < len(header_positions) else len(lines)
        end_page = page_at_line.get(end_idx - 1, start_page)

        content_lines = lines[start_idx + 1 : end_idx]
        content = "\n".join(content_lines).strip()

        sections.append(Section(
            title=title,
            content=content,
            start_page=start_page,
            end_page=end_page,
        ))

    return ChunkResult(sections=sections, total_pages=max_page)


def _is_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _PAGE_MARKER_RE.match(stripped):
        return False
    # Must be reasonably short (headers aren't paragraphs)
    if len(stripped) > 120:
        return False
    return any(p.match(stripped) for p in _HEADER_PATTERNS)
