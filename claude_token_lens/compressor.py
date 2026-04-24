"""Coding-session-aware prompt compression strategies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from .estimator import count_tokens


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class CompressorConfig:
    # Stack trace: keep first N and last N frames
    stack_head_lines: int = 3
    stack_tail_lines: int = 5

    # Code blocks: collapse runs of blank lines
    max_blank_lines_in_code: int = 1

    # Strip single-line comments from code blocks (// and #)
    strip_code_comments: bool = False

    # Warn (but don't auto-strip) when an inline code block exceeds this many tokens
    large_code_warn_tokens: int = 300

    # Collapse repeated whitespace in plain text
    collapse_whitespace: bool = True

    # Minimum tokens saved to bother reporting
    report_threshold_tokens: int = 20


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class CompressionResult:
    original: str
    compressed: str
    original_tokens: int
    compressed_tokens: int
    strategies_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def saved(self) -> int:
        return self.original_tokens - self.compressed_tokens

    @property
    def ratio(self) -> float:
        if self.original_tokens == 0:
            return 1.0
        return self.compressed_tokens / self.original_tokens

    @property
    def pct_saved(self) -> float:
        return (1.0 - self.ratio) * 100


# ── Stack-trace compression ───────────────────────────────────────────────────

# Matches common stack trace patterns across Python, Node.js, Java, Go, Rust
_STACK_FRAME_RE = re.compile(
    r"^\s*(at |File \"|  File \"|#\d+|goroutine |\s+\d+:)",
    re.MULTILINE,
)

_TRACEBACK_START_RE = re.compile(
    r"(Traceback \(most recent call last\):|Error:|Exception:|"
    r"panic:|fatal error:|FAIL\t)",
    re.IGNORECASE,
)


def _compress_stack_trace(text: str, cfg: CompressorConfig) -> Tuple[str, bool]:
    """
    Condense long stack traces while preserving the error message and key frames.
    Returns (compressed_text, was_modified).

    Handles Python, Node.js, Java, Go, and Rust stack traces.
    Frame blocks are collected by treating any indented line (spaces/tabs) or
    a line matching the frame pattern as part of the trace block.
    """
    lines = text.splitlines(keepends=True)
    result_lines: List[str] = []
    i = 0
    modified = False

    while i < len(lines):
        if not _TRACEBACK_START_RE.search(lines[i]):
            result_lines.append(lines[i])
            i += 1
            continue

        # Found a traceback header — collect the frame block
        block_start = i
        i += 1
        while i < len(lines) and (
            _STACK_FRAME_RE.match(lines[i])
            or lines[i].strip() == ""
            or (lines[i] and lines[i][0] in (" ", "\t"))  # indented continuation lines
        ):
            i += 1
        block_end = i  # exclusive

        frame_lines = lines[block_start:block_end]
        # Count "real" frame anchor lines (File/at/goroutine) for the omit decision
        anchor_count = sum(1 for l in frame_lines if _STACK_FRAME_RE.match(l))

        if anchor_count > cfg.stack_head_lines + cfg.stack_tail_lines:
            # Identify anchor positions so we can keep N from head and N from tail
            anchor_indices = [
                idx for idx, l in enumerate(frame_lines) if _STACK_FRAME_RE.match(l)
            ]
            head_cutoff = anchor_indices[cfg.stack_head_lines - 1] + 1 if cfg.stack_head_lines else 0
            tail_start = anchor_indices[-cfg.stack_tail_lines] if cfg.stack_tail_lines else len(frame_lines)

            omitted = anchor_count - cfg.stack_head_lines - cfg.stack_tail_lines
            kept = (
                frame_lines[:head_cutoff]
                + [f"    ... [{omitted} frames omitted] ...\n"]
                + frame_lines[tail_start:]
            )
            result_lines.extend(kept)
            modified = True
        else:
            result_lines.extend(frame_lines)

    return "".join(result_lines), modified


# ── Code-block compression ────────────────────────────────────────────────────

_CODE_FENCE_RE = re.compile(r"^```[\w]*$", re.MULTILINE)

# Single-line comment patterns (language-aware would be better, but this covers 90%)
_COMMENT_LINE_RE = re.compile(r"^\s*(//|#)[^\n]*\n?", re.MULTILINE)
_INLINE_COMMENT_RE = re.compile(r"\s+(//|#)[^\n]+$", re.MULTILINE)


def _compress_code_block(code: str, cfg: CompressorConfig) -> str:
    """Compress a single fenced code block's content."""
    # Collapse consecutive blank lines
    max_blanks = "\n" * (cfg.max_blank_lines_in_code + 1)
    while "\n" + max_blanks in code:
        code = code.replace("\n" + max_blanks, max_blanks)

    if cfg.strip_code_comments:
        code = _COMMENT_LINE_RE.sub("", code)
        code = _INLINE_COMMENT_RE.sub("", code)

    return code


def _compress_code_blocks(
    text: str, cfg: CompressorConfig
) -> Tuple[str, bool, List[str]]:
    """Process all fenced code blocks in the text."""
    parts = _CODE_FENCE_RE.split(text)
    if len(parts) < 3:
        return text, False, []

    warnings: List[str] = []
    result: List[str] = []
    modified = False

    fences = _CODE_FENCE_RE.findall(text)
    # parts: [before_first, content1, between, content2, ...]
    # Odd-indexed parts (1, 3, 5…) are inside fences
    for idx, part in enumerate(parts):
        if idx % 2 == 1:  # inside a code fence
            compressed = _compress_code_block(part, cfg)
            if compressed != part:
                modified = True
            token_count = count_tokens(compressed)
            if token_count > cfg.large_code_warn_tokens:
                warnings.append(
                    f"Large code block (~{token_count} tokens). "
                    "Consider referencing the file path instead of pasting inline."
                )
            result.append(compressed)
        else:
            result.append(part)

    # Re-interleave fences
    # Reconstruct by simple concatenation — no extra newlines
    output = result[0]
    for fence, content in zip(fences, result[1:]):
        output += fence + content

    return output if modified else text, modified, warnings


# ── Whitespace compression ────────────────────────────────────────────────────

def _compress_whitespace(text: str) -> Tuple[str, bool]:
    """Collapse runs of blank lines (outside code blocks) to at most 2."""
    # Only outside code fences
    segments = _CODE_FENCE_RE.split(text)
    if len(segments) < 2:
        compressed = re.sub(r"\n{3,}", "\n\n", text)
        return compressed, compressed != text

    fences = _CODE_FENCE_RE.findall(text)
    result: List[str] = []
    for idx, seg in enumerate(segments):
        if idx % 2 == 0:  # outside code fence
            result.append(re.sub(r"\n{3,}", "\n\n", seg))
        else:
            result.append(seg)

    output_parts: List[str] = [result[0]]
    for fence, content in zip(fences, result[1:]):
        output_parts.append(fence)
        output_parts.append(content)

    output = "\n".join(output_parts)
    return output, output != text


# ── Main entry point ──────────────────────────────────────────────────────────

def compress_prompt(text: str, cfg: CompressorConfig | None = None) -> CompressionResult:
    """
    Apply all enabled compression strategies to a prompt.
    Strategies are applied in order; each works on the output of the previous.
    """
    if cfg is None:
        cfg = CompressorConfig()

    original_tokens = count_tokens(text)
    current = text
    strategies: List[str] = []
    warnings: List[str] = []

    # 1. Stack trace compression
    current, changed = _compress_stack_trace(current, cfg)
    if changed:
        strategies.append("stack-trace")

    # 2. Code block compression
    current, changed, code_warnings = _compress_code_blocks(current, cfg)
    if changed:
        strategies.append("code-blocks")
    warnings.extend(code_warnings)

    # 3. Whitespace compression
    if cfg.collapse_whitespace:
        current, changed = _compress_whitespace(current)
        if changed:
            strategies.append("whitespace")

    compressed_tokens = count_tokens(current)

    return CompressionResult(
        original=text,
        compressed=current,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        strategies_applied=strategies,
        warnings=warnings,
    )
