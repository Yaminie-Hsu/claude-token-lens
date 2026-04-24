#!/usr/bin/env python3
"""
token-lens statusline script for Claude Code.

Receives session JSON on stdin, queries the token-lens DB for that session,
and outputs a compact status line to stdout.
"""

from __future__ import annotations

import json
import sys
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

    try:
        stats = get_session_stats(session_id)
    except Exception:
        return

    n = stats["total_events"]
    original = stats["total_original"]
    saved = stats["total_saved"]
    pct = stats["avg_pct_saved"]

    if n == 0:
        print("lens: no prompts yet")
        return

    # Compact token formatter
    def fmt(t: int) -> str:
        return f"{t/1000:.1f}k" if t >= 1000 else str(t)

    if saved > 0:
        line = f"lens  {n} prompts · {fmt(original)} tok · saved {fmt(saved)} ({pct:.0f}%)"
    else:
        line = f"lens  {n} prompts · {fmt(original)} tok"

    print(line)


if __name__ == "__main__":
    main()
