"""Extract document outline and key fields.

Outline  — section titles with page numbers (token-efficient TOC to feed
           Claude before asking it to deep-dive specific sections).

Key info — contract parties, effective dates, amounts, governing law.
           Rule-based, no API calls required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chunker import chunk_document, ChunkResult
from ..estimator import count_tokens, format_tokens


@dataclass
class DocumentSummary:
    outline: str           # Compact TOC string
    key_fields: dict       # Extracted metadata
    total_tokens: int
    total_pages: int
    chunk_result: ChunkResult

    def to_markdown(self) -> str:
        lines = [self.outline, ""]
        if self.key_fields:
            lines.append("## 关键信息摘取\n")
            for k, v in self.key_fields.items():
                if v:
                    lines.append(f"- **{k}**：{v}")
        lines.append(f"\n*文档共 {self.total_pages} 页，约 {format_tokens(self.total_tokens)} tokens*")
        return "\n".join(lines)


# ── Key field extraction (rule-based) ────────────────────────────────────────

# Patterns keyed by field label
_FIELD_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("甲方", re.compile(r"甲\s*方[：:]\s*([^\n，,。]{2,30})")),
    ("乙方", re.compile(r"乙\s*方[：:]\s*([^\n，,。]{2,30})")),
    ("丙方", re.compile(r"丙\s*方[：:]\s*([^\n，,。]{2,30})")),
    ("合同金额", re.compile(
        r"(?:合同总?金额|总价款|合同价款)[^\d元￥]{0,10}"
        r"((?:人民币)?[\d,，.]+(?:\s*万)?(?:\s*元)?)"
    )),
    ("签署日期", re.compile(
        r"(?:签订|签署|订立)(?:日期|于|时间)[^\d年]{0,5}"
        r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})"
    )),
    ("生效日期", re.compile(
        r"(?:生效|起效)(?:日期|于|时间)[^\d年]{0,5}"
        r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})"
    )),
    ("履行期限", re.compile(r"(?:履行期限|合同期限|有效期)[：:\s]*([^\n。]{4,40})")),
    ("争议管辖", re.compile(r"(?:争议解决|管辖法院|仲裁机构)[：:\s]*([^\n。]{4,40})")),
    ("适用法律", re.compile(r"(?:适用法律|准据法)[：:\s]*([^\n。]{4,30})")),
]


def extract_key_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for label, pattern in _FIELD_PATTERNS:
        m = pattern.search(text)
        if m:
            fields[label] = m.group(1).strip()
    return fields


# ── Main ─────────────────────────────────────────────────────────────────────

def summarize(text: str) -> DocumentSummary:
    chunk_result = chunk_document(text)
    key_fields = extract_key_fields(text)

    return DocumentSummary(
        outline=chunk_result.outline(),
        key_fields=key_fields,
        total_tokens=chunk_result.total_tokens,
        total_pages=chunk_result.total_pages,
        chunk_result=chunk_result,
    )
