"""Extract a chronological event timeline from one or more documents.

Each event records:
  - Normalized date (YYYY-MM-DD or YYYY-MM)
  - Event description (the sentence(s) containing the date)
  - Source filename
  - Page number in the original PDF

Supported date formats
  ─ Chinese:    2024年3月15日 / 2024年3月 / 二〇二四年三月十五日
  ─ ISO / dash: 2024-03-15 / 2024/03/15
  ─ English:    March 15, 2024 / 15 March 2024
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


# ── Date extraction ───────────────────────────────────────────────────────────

# Chinese digit → Arabic
_CN_DIGIT = {
    "〇": "0", "零": "0",
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9",
    "十": "10",  # handled specially in _cn_to_int
}

_MONTH_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Pattern groups — all with named groups year/month/day where applicable
_DATE_PATTERNS: list[tuple[str, re.Pattern]] = [
    # 2024年3月15日 or 2024年03月15日
    ("cn_full", re.compile(
        r"([零〇一二三四五六七八九十百千\d]{2,4})年"
        r"([一二三四五六七八九十\d]{1,2})月"
        r"([一二三四五六七八九十\d]{1,2})日"
    )),
    # 2024年3月 (no day)
    ("cn_ym", re.compile(
        r"([零〇一二三四五六七八九十百千\d]{2,4})年"
        r"([一二三四五六七八九十\d]{1,2})月"
        r"(?![一二三四五六七八九十\d])"
    )),
    # 2024-03-15 or 2024/03/15
    ("iso", re.compile(r"(?<!\d)((?:19|20)\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])(?!\d)")),
    # March 15, 2024  /  15 March 2024
    ("en_mdy", re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+(\d{1,2}),?\s+((?:19|20)\d{2})\b",
        re.IGNORECASE,
    )),
    ("en_dmy", re.compile(
        r"\b(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+((?:19|20)\d{2})\b",
        re.IGNORECASE,
    )),
]

_PAGE_MARKER_RE = re.compile(r"─+\s*\[第\s*(\d+)\s*页\]")


def _cn_to_int(s: str) -> int | None:
    """Convert a short Chinese numeral string to int (handles 一—十九 range)."""
    s = s.strip()
    # Already Arabic
    if s.isdigit():
        return int(s)
    result = ""
    for ch in s:
        result += _CN_DIGIT.get(ch, ch)
    if result.isdigit():
        return int(result)
    return None


def _parse_date(fmt: str, m: re.Match) -> tuple[str, bool]:
    """
    Return (normalized_date_str, has_day).
    normalized_date_str is YYYY-MM-DD or YYYY-MM.
    """
    try:
        if fmt in ("cn_full", "cn_ym"):
            y = _cn_to_int(m.group(1))
            mo = _cn_to_int(m.group(2))
            if fmt == "cn_full":
                d = _cn_to_int(m.group(3))
                if y and mo and d:
                    return f"{y:04d}-{mo:02d}-{d:02d}", True
            else:
                if y and mo:
                    return f"{y:04d}-{mo:02d}", False

        elif fmt == "iso":
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{d:02d}", True

        elif fmt == "en_mdy":
            mo = _MONTH_EN.get(m.group(1).lower())
            d, y = int(m.group(2)), int(m.group(3))
            if mo:
                return f"{y:04d}-{mo:02d}-{d:02d}", True

        elif fmt == "en_dmy":
            d = int(m.group(1))
            mo = _MONTH_EN.get(m.group(2).lower())
            y = int(m.group(3))
            if mo:
                return f"{y:04d}-{mo:02d}-{d:02d}", True

    except (ValueError, TypeError):
        pass
    return "", False


# ── Event extraction ─────────────────────────────────────────────────────────

@dataclass
class TimelineEvent:
    date_str: str          # YYYY-MM-DD or YYYY-MM
    has_day: bool
    description: str       # surrounding sentence(s)
    source_file: str       # filename
    page: int              # page number in original PDF


def extract_events(text: str, source_file: str) -> list[TimelineEvent]:
    """Extract all datable events from a document text (with page markers)."""
    events: list[TimelineEvent] = []
    # Track current page as we scan
    page_of_char: list[int] = _build_page_index(text)

    for fmt, pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            date_str, has_day = _parse_date(fmt, m)
            if not date_str:
                continue

            # Sanity-check year range
            year = int(date_str[:4])
            if not (1900 <= year <= 2100):
                continue

            # Extract surrounding sentence (up to 200 chars each side)
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            snippet = text[start:end]
            # Clean page markers from snippet
            snippet = _PAGE_MARKER_RE.sub("", snippet).strip()
            # Take the sentence containing the match
            description = _extract_sentence(snippet, m.start() - start)

            page = page_of_char[m.start()] if m.start() < len(page_of_char) else 1

            events.append(TimelineEvent(
                date_str=date_str,
                has_day=has_day,
                description=description,
                source_file=source_file,
                page=page,
            ))

    # Deduplicate: same date + same page → keep longest description
    return _deduplicate(events)


def _build_page_index(text: str) -> list[int]:
    """For each character position, return the current page number."""
    result = [1] * len(text)
    current = 1
    for m in _PAGE_MARKER_RE.finditer(text):
        current = int(m.group(1))
        for i in range(m.start(), len(text)):
            result[i] = current
            break  # only update from this position onward in a second pass
    # Simpler O(n) pass
    current = 1
    for i, ch in enumerate(text):
        # Check if a page marker starts here
        pm = _PAGE_MARKER_RE.match(text[i:i+60])
        if pm:
            current = int(pm.group(1))
        result[i] = current
    return result


def _extract_sentence(text: str, match_offset: int) -> str:
    """Return the sentence containing match_offset."""
    # Sentence boundaries: 。！？.!? and newlines
    boundary = re.compile(r"[。！？.!?\n]")
    # Find sentence start
    start = 0
    for m in boundary.finditer(text[:match_offset]):
        start = m.end()
    # Find sentence end
    end = len(text)
    m = boundary.search(text, match_offset)
    if m:
        end = m.end()

    sentence = text[start:end].strip()
    # Trim very long sentences
    if len(sentence) > 300:
        sentence = sentence[:300] + "…"
    return sentence


def _deduplicate(events: list[TimelineEvent]) -> list[TimelineEvent]:
    seen: dict[tuple, TimelineEvent] = {}
    for ev in events:
        key = (ev.date_str, ev.source_file, ev.page)
        if key not in seen or len(ev.description) > len(seen[key].description):
            seen[key] = ev
    return list(seen.values())


# ── Multi-document timeline ───────────────────────────────────────────────────

def build_timeline(
    documents: list[tuple[str, str]],  # [(filename, text), ...]
) -> str:
    """
    Build a markdown timeline table from multiple documents.
    documents: list of (source_filename, extracted_text) tuples.
    """
    all_events: list[TimelineEvent] = []
    for filename, text in documents:
        all_events.extend(extract_events(text, source_file=filename))

    if not all_events:
        return "未在文档中检测到可识别的日期。"

    # Sort: YYYY-MM-DD sorts lexicographically; YYYY-MM goes before YYYY-MM-DD
    all_events.sort(key=lambda e: e.date_str)

    lines = [
        "## 事件时间线\n",
        f"| {'日期':<12} | {'事件摘要':<45} | {'来源文件':<20} | 页码 |",
        f"|{'-'*14}|{'-'*47}|{'-'*22}|------|",
    ]

    for ev in all_events:
        desc = ev.description.replace("|", "｜")
        if len(desc) > 44:
            desc = desc[:43] + "…"
        fname = Path(ev.source_file).name
        if len(fname) > 19:
            fname = fname[:18] + "…"
        lines.append(
            f"| {ev.date_str:<12} | {desc:<45} | {fname:<20} | 第 {ev.page} 页 |"
        )

    lines.append(f"\n*共检测到 {len(all_events)} 个时间节点，来自 {len(documents)} 份文档。*")
    return "\n".join(lines)
