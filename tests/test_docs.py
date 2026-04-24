"""Tests for document processing modules."""

from claude_token_lens.docs.cleaner import clean_document
from claude_token_lens.docs.chunker import chunk_document, _is_header
from claude_token_lens.docs.timeline import extract_events, build_timeline
from claude_token_lens.docs.summarizer import extract_key_fields


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_doc(pages: list[str]) -> str:
    """Build a fake extracted document with page markers."""
    parts = []
    for i, content in enumerate(pages, start=1):
        marker = f"─── [第 {i} 页] " + "─" * 40
        parts.append(f"{marker}\n\n{content}")
    return "\n\n".join(parts)


HEADER_TEXT = "保密文件  XX律师事务所  2024"
FOOTER_TEXT = "未经授权不得复制"

SAMPLE_DOC = _make_doc([
    f"{HEADER_TEXT}\n\n第一条　总则\n本合同由甲乙双方协商一致签订。\n\n{FOOTER_TEXT}",
    f"{HEADER_TEXT}\n\n第二条　定义\n本合同所称产品是指……\n\n{FOOTER_TEXT}",
    f"{HEADER_TEXT}\n\n第三条　权利义务\n甲方应于2024年3月1日前完成交付。\n\n{FOOTER_TEXT}",
    f"{HEADER_TEXT}\n\n第四条　违约责任\n违约方应支付合同总金额5%的违约金。\n\n{FOOTER_TEXT}",
    f"{HEADER_TEXT}\n\n第五条　争议解决\n本合同适用中华人民共和国法律。\n\n{FOOTER_TEXT}",
])


# ── Cleaner ───────────────────────────────────────────────────────────────────

def test_repeated_headers_removed():
    result = clean_document(SAMPLE_DOC)
    assert HEADER_TEXT not in result.text
    assert FOOTER_TEXT not in result.text
    assert len(result.removed_patterns) >= 1


def test_page_markers_preserved():
    result = clean_document(SAMPLE_DOC)
    assert "[第 1 页]" in result.text
    assert "[第 3 页]" in result.text


def test_content_preserved():
    result = clean_document(SAMPLE_DOC)
    assert "第一条" in result.text
    assert "第三条" in result.text


def test_short_document_unchanged():
    short = _make_doc(["内容A", "内容B"])
    result = clean_document(short)
    assert result.removed_patterns == []


# ── Chunker ───────────────────────────────────────────────────────────────────

def test_chinese_legal_headers_detected():
    assert _is_header("第一条　总则")
    assert _is_header("第八条　违约责任")
    assert _is_header("一、总则")
    assert _is_header("（一）基本原则")


def test_numeric_headers_detected():
    assert _is_header("1. 概述")
    assert _is_header("8.3 违约条款")


def test_non_headers_not_detected():
    assert not _is_header("本合同由甲乙双方协商一致签订，具有法律效力。")
    assert not _is_header("─── [第 3 页] ───────────")
    assert not _is_header("")


def test_chunk_sections_found():
    result = chunk_document(SAMPLE_DOC)
    assert len(result.sections) >= 4
    titles = [s.title for s in result.sections]
    assert any("第一条" in t for t in titles)
    assert any("第三条" in t for t in titles)


def test_chunk_page_ranges():
    result = chunk_document(SAMPLE_DOC)
    for section in result.sections:
        assert section.start_page >= 1
        assert section.end_page >= section.start_page


def test_chunk_outline_contains_pages():
    result = chunk_document(SAMPLE_DOC)
    outline = result.outline()
    assert "第" in outline and "页" in outline


# ── Timeline ─────────────────────────────────────────────────────────────────

TIMELINE_DOC = _make_doc([
    "甲方于2023年3月1日签署了《框架协议》，协议有效期三年。",
    "乙方在2023年6月15日提交了首期交付物，甲方于2023-09-30发出验收意见。",
    "因乙方未完成整改，甲方于2024年1月10日发出违约通知函。",
])


def test_events_extracted():
    events = extract_events(TIMELINE_DOC, source_file="test.pdf")
    dates = [e.date_str for e in events]
    assert "2023-03-01" in dates
    assert "2023-06-15" in dates
    assert "2023-09-30" in dates
    assert "2024-01-10" in dates


def test_events_have_page_numbers():
    events = extract_events(TIMELINE_DOC, source_file="test.pdf")
    for ev in events:
        assert ev.page >= 1


def test_timeline_sorted():
    events = extract_events(TIMELINE_DOC, source_file="test.pdf")
    dates = [e.date_str for e in sorted(events, key=lambda e: e.date_str)]
    assert dates == sorted(dates)


def test_build_timeline_markdown():
    table = build_timeline([("test.pdf", TIMELINE_DOC)])
    assert "## 事件时间线" in table
    assert "2023-03-01" in table
    assert "第" in table and "页" in table


def test_multi_document_timeline():
    doc2 = _make_doc(["合同于2022年12月1日正式生效。"])
    table = build_timeline([("合同.pdf", TIMELINE_DOC), ("背景.pdf", doc2)])
    assert "2022-12-01" in table
    assert "2023-03-01" in table
    # 2022 should appear before 2023
    assert table.index("2022-12-01") < table.index("2023-03-01")


# ── Key field extraction ──────────────────────────────────────────────────────

CONTRACT_TEXT = """
甲方：北京科技有限公司
乙方：上海贸易有限公司
合同金额：人民币150万元
签署日期：2024年1月15日
争议解决：提交北京仲裁委员会仲裁
适用法律：中华人民共和国法律
"""


def test_key_fields_extracted():
    fields = extract_key_fields(CONTRACT_TEXT)
    assert "甲方" in fields
    assert "北京科技有限公司" in fields["甲方"]
    assert "乙方" in fields
    assert "合同金额" in fields


def test_missing_fields_not_in_result():
    fields = extract_key_fields("这是一份没有结构化信息的文本。")
    assert fields == {} or all(v == "" for v in fields.values())
