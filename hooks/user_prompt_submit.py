#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook.

Reads the hook event from stdin (JSON), compresses the prompt,
writes the updated prompt as JSON to stdout, and prints a brief
compression report to stderr.

Install via setup.py or add manually to settings.json:
  {
    "hooks": {
      "UserPromptSubmit": [{
        "hooks": [{"type": "command", "command": "python3 /path/to/hooks/user_prompt_submit.py"}]
      }]
    }
  }
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running the hook directly without installing the package
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from claude_token_lens.advisor import build_report
from claude_token_lens.compressor import CompressorConfig, compress_prompt
from claude_token_lens.tracker import get_stats, record_event

# ── Load user config (optional ~/.claude-token-lens/config.json) ─────────────

_CONFIG_PATH = Path(os.environ.get("CLAUDE_TOKEN_LENS_DIR", "~/.claude-token-lens")).expanduser() / "config.json"

def _load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _build_compressor_config(user_cfg: dict) -> CompressorConfig:
    c = user_cfg.get("compressor", {})
    return CompressorConfig(
        stack_head_lines=c.get("stack_head_lines", 3),
        stack_tail_lines=c.get("stack_tail_lines", 5),
        max_blank_lines_in_code=c.get("max_blank_lines_in_code", 1),
        strip_code_comments=c.get("strip_code_comments", False),
        large_code_warn_tokens=c.get("large_code_warn_tokens", 300),
        collapse_whitespace=c.get("collapse_whitespace", True),
        report_threshold_tokens=c.get("report_threshold_tokens", 20),
    )


# ── Hook entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    raw = sys.stdin.read()

    # Gracefully handle empty or non-JSON input
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        print("{}", flush=True)
        return

    prompt: str = event.get("prompt", "")
    if not prompt:
        print("{}", flush=True)
        return

    session_id: str = event.get("session_id", "")
    cwd: str = event.get("cwd", "")
    model: str = os.environ.get("CLAUDE_MODEL", "sonnet").lower()

    user_cfg = _load_config()
    cfg = _build_compressor_config(user_cfg)

    result = compress_prompt(prompt, cfg)

    # Always record every prompt so stats reflect real token throughput
    try:
        record_event(
            original_tokens=result.original_tokens,
            compressed_tokens=result.compressed_tokens,
            strategies=result.strategies_applied,
            session_id=session_id,
            cwd=cwd,
        )
    except Exception:
        pass  # never block on tracking errors

    if result.saved >= cfg.report_threshold_tokens:
        # Cumulative session tokens for context-window advisories
        try:
            stats = get_stats(days=1)
            cumulative = stats.get("total_compressed", 0)
        except Exception:
            cumulative = 0

        report = build_report(
            original_tokens=result.original_tokens,
            compressed_tokens=result.compressed_tokens,
            strategies=result.strategies_applied,
            warnings=result.warnings,
            cumulative_tokens=cumulative,
            model=model,
        )
        print(report, file=sys.stderr, flush=True)

        # Return the compressed prompt to Claude Code
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "updatedPrompt": result.compressed,
            }
        }
    else:
        # Nothing worth compressing — pass through, but still show warnings
        if result.warnings:
            for w in result.warnings:
                print(f"[token-lens] ⚠  {w}", file=sys.stderr, flush=True)
        output = {}

    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
