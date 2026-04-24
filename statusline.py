#!/usr/bin/env python3
"""
token-lens statusline script for Claude Code.

Receives session JSON on stdin, queries the token-lens DB for that session,
and outputs a compact status line to stdout.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from claude_token_lens.tracker import get_session_stats


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    session_id: str = data.get("session_id", "")
    if not session_id:
        return

    # Read token counts and cost directly from the session JSON
    ctx = data.get("context_window", {})
    in_tok = ctx.get("total_input_tokens", 0)
    out_tok = ctx.get("total_output_tokens", 0)
    used_pct = ctx.get("used_percentage", 0)
    cost_usd = data.get("cost", {}).get("total_cost_usd", 0.0)

    # Rate limit (5-hour window)
    five_hour = data.get("rate_limits", {}).get("five_hour", {})
    usage_pct = five_hour.get("used_percentage", 0)
    resets_at = five_hour.get("resets_at", 0)
    if resets_at:
        remaining = max(0, int(resets_at - time.time()))
        h, m = divmod(remaining // 60, 60)
        resets_str = f"· Resets in {h}hr {m}min" if h else f"· Resets in {m}min"
    else:
        resets_str = ""

    # Read compression savings from DB
    try:
        stats = get_session_stats(session_id)
        saved = stats["total_saved"]
        saved_pct = stats["avg_pct_saved"]
    except Exception:
        saved = 0
        saved_pct = 0.0

    def fmt(t: int) -> str:
        return f"{t/1000:.1f}k" if t >= 1000 else str(t)

    if used_pct >= 80:
        ctx_str = f"\033[31mctx {used_pct}% · /compact or /clear\033[0m"  # red (ctx part only)
    elif used_pct >= 50:
        ctx_str = f"\033[33mctx {used_pct}%\033[0m"   # yellow
    else:
        ctx_str = f"ctx {used_pct}%"

    usage_str = f"usage {usage_pct}% {resets_str}".strip() if usage_pct else ""

    parts = [
        f"lens  {fmt(in_tok)}↑ {fmt(out_tok)}↓",
        ctx_str,
    ]
    if usage_str:
        parts.append(usage_str)
    parts.append(f"${cost_usd:.4f}")
    if saved > 0:
        parts.append(f"saved {fmt(saved)} ({saved_pct:.0f}%)")

    print(" · ".join(parts))


if __name__ == "__main__":
    main()
