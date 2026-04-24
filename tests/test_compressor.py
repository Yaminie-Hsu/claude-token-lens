"""Tests for the compression strategies."""

import pytest
from claude_token_lens.compressor import (
    CompressorConfig,
    compress_prompt,
    _compress_stack_trace,
    _compress_code_blocks,
    _compress_whitespace,
)


# ── Stack trace ───────────────────────────────────────────────────────────────

PYTHON_TRACEBACK = """\
Traceback (most recent call last):
  File "app.py", line 10, in <module>
    result = process(data)
  File "app.py", line 20, in process
    return transform(x)
  File "app.py", line 30, in transform
    raise ValueError("bad input")
  File "lib/util.py", line 5, in helper
    return inner()
  File "lib/util.py", line 12, in inner
    return x / 0
  File "lib/util.py", line 18, in inner2
    pass
ValueError: bad input
"""

NODE_TRACEBACK = """\
Error: Cannot read properties of undefined
    at Object.processRequest (/app/server.js:42:15)
    at Layer.handle [as handle_request] (/app/node_modules/express/lib/router/layer.js:95:5)
    at next (/app/node_modules/express/lib/router/route.js:144:13)
    at Route.dispatch (/app/node_modules/express/lib/router/route.js:114:3)
    at Layer.handle [as handle_request] (/app/node_modules/express/lib/router/layer.js:95:5)
    at /app/node_modules/express/lib/router/index.js:284:15
    at Function.process_params (/app/node_modules/express/lib/router/index.js:346:12)
    at next (/app/node_modules/express/lib/router/index.js:280:10)
    at /app/routes/api.js:22:5
"""


def test_python_traceback_compressed():
    cfg = CompressorConfig(stack_head_lines=2, stack_tail_lines=2)
    result, modified = _compress_stack_trace(PYTHON_TRACEBACK, cfg)
    assert modified
    assert "frames omitted" in result
    assert "ValueError: bad input" in result  # error line preserved


def test_node_traceback_compressed():
    cfg = CompressorConfig(stack_head_lines=2, stack_tail_lines=2)
    result, modified = _compress_stack_trace(NODE_TRACEBACK, cfg)
    assert modified
    assert "frames omitted" in result
    assert "Cannot read properties" in result


def test_short_traceback_not_modified():
    short = "Error: something\n  at foo (bar.js:1:1)\n  at baz (qux.js:2:2)\n"
    cfg = CompressorConfig(stack_head_lines=3, stack_tail_lines=5)
    _, modified = _compress_stack_trace(short, cfg)
    assert not modified


# ── Code blocks ───────────────────────────────────────────────────────────────

def test_code_block_blank_lines_collapsed():
    text = "Look at this:\n```python\ndef foo():\n\n\n\n    pass\n```"
    result, modified, _ = _compress_code_blocks(text, CompressorConfig())
    assert modified
    # Should have at most 1 consecutive blank line inside the fence
    assert "\n\n\n" not in result


def test_code_block_comments_stripped():
    text = "```python\n# this is a comment\nx = 1\n# another comment\n```"
    cfg = CompressorConfig(strip_code_comments=True)
    result, modified, _ = _compress_code_blocks(text, cfg)
    assert modified
    assert "# this is a comment" not in result
    assert "x = 1" in result


def test_large_code_block_warning():
    # Generate a large code block
    big_code = "```python\n" + ("x = 1  # line\n" * 100) + "```"
    _, _, warnings = _compress_code_blocks(big_code, CompressorConfig(large_code_warn_tokens=50))
    assert any("Large code block" in w for w in warnings)


def test_no_code_block_unchanged():
    text = "Just some plain text without any fences."
    result, modified, _ = _compress_code_blocks(text, CompressorConfig())
    assert not modified
    assert result == text


# ── Whitespace ────────────────────────────────────────────────────────────────

def test_excessive_blank_lines_collapsed():
    text = "Line one\n\n\n\n\nLine two"
    result, modified = _compress_whitespace(text)
    assert modified
    assert "\n\n\n" not in result
    assert "Line one" in result
    assert "Line two" in result


def test_whitespace_inside_code_fence_preserved():
    text = "```python\n\n\n\nx = 1\n```"
    result, _ = _compress_whitespace(text)
    # Code fence content should not be touched by whitespace compressor
    assert "\n\n\n\n" in result


# ── Full pipeline ─────────────────────────────────────────────────────────────

def test_full_compress_reduces_tokens():
    # Build a traceback with >8 frames (default threshold = stack_head + stack_tail)
    long_trace = "Traceback (most recent call last):\n"
    for i in range(12):
        long_trace += f'  File "app.py", line {i * 10}, in fn_{i}\n'
        long_trace += f"    do_thing_{i}()\n"
    long_trace += "ValueError: something went wrong\n"

    # Code block with excessive blank lines
    code_block = (
        "```python\n"
        "import os\n\n\n\n\n"
        "def main():\n\n\n\n"
        "    pass\n"
        "```"
    )

    prompt = f"I'm getting this error:\n\n{long_trace}\n\nHere's my code:\n\n{code_block}\n\n\n\nPlease help."
    result = compress_prompt(prompt)
    assert result.saved > 0
    assert len(result.strategies_applied) > 0


def test_plain_prompt_unchanged():
    prompt = "What is a linked list?"
    result = compress_prompt(prompt)
    assert result.compressed == prompt
    assert result.saved == 0
