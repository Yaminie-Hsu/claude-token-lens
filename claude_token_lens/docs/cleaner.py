"""Remove repeated headers/footers from extracted document text.

Strategy:
  1. Split text into pages using the [第 N 页] markers.
  2. For each page, examine the first and last few lines.
  3. Lines that appear verbatim (or near-verbatim) on > REPEAT_THRESHOLD of
     all pages are classified as headers or footers.
  4. Remove those lines from every page — but keep the page markers intact.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# A line must appear on this fraction of pages to be considered a header/footer
REPEAT_THRESHOLD = 0.4

# How many lines from the top / bottom of each page to inspect
SCAN_LINES = 4

# Regex that matches our page markers — never touch these
_PAGE_MARKER_RE = re.compile(r"^─+\s*\[第\s*\d+\s*页\]")


@dataclass
class CleanResult:
    text: str
    removed_patterns: list[str]   # headers/footers that were stripped
    pages_processed: int


def clean_document(text: str) -> CleanResult:
    """
    Detect and remove repeated headers/footers.
    Page markers are always preserved.
    """
    pages = _split_pages(text)
    if len(pages) < 3:
        # Too few pages to reliably detect repetition — return as-is
        return CleanResult(text=text, removed_patterns=[], pages_processed=len(pages))

    repeated = _find_repeated_lines(pages)

    if not repeated:
        return CleanResult(text=text, removed_patterns=[], pages_processed=len(pages))

    cleaned_pages = [_remove_lines(page, repeated) for page in pages]
    return CleanResult(
        text="\n\n".join(cleaned_pages),
        removed_patterns=sorted(repeated),
        pages_processed=len(pages),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_pages(text: str) -> list[str]:
    """Split on page markers, keeping each marker as the first line of its page."""
    parts = re.split(r"(?=^─+\s*\[第\s*\d+\s*页\])", text, flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def _candidate_lines(page: str) -> list[str]:
    """Return the first and last SCAN_LINES non-marker, non-blank lines of a page."""
    lines = [
        l.strip()
        for l in page.splitlines()
        if l.strip() and not _PAGE_MARKER_RE.match(l)
    ]
    candidates = lines[:SCAN_LINES] + lines[-SCAN_LINES:]
    return [l for l in candidates if len(l) > 2]   # ignore very short lines


def _find_repeated_lines(pages: list[str]) -> set[str]:
    counter: Counter = Counter()
    for page in pages:
        # Use a set so the same line only counts once per page
        for line in set(_candidate_lines(page)):
            counter[line] += 1

    threshold = len(pages) * REPEAT_THRESHOLD
    return {line for line, count in counter.items() if count >= threshold}


def _remove_lines(page: str, to_remove: set[str]) -> str:
    kept: list[str] = []
    for line in page.splitlines():
        stripped = line.strip()
        if stripped in to_remove:
            continue
        kept.append(line)
    # Collapse runs of blank lines left behind after removal
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(kept))
    return result.strip()
