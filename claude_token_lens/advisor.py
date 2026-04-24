"""Real-time usage advisories based on cumulative session context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .estimator import count_tokens, format_tokens


# Claude Code context windows (tokens)
CONTEXT_WINDOWS = {
    "opus":   200_000,
    "sonnet": 200_000,
    "haiku":  200_000,
}

# Thresholds at which to suggest action
COMPACT_SUGGEST_PCT = 0.60   # suggest /compact
COMPACT_URGENT_PCT  = 0.80   # strongly suggest /compact
CLEAR_SUGGEST_PCT   = 0.90   # suggest /clear


@dataclass
class Advisory:
    level: str        # "info" | "warn" | "urgent"
    message: str
    command: Optional[str] = None  # suggested Claude Code command


def check_context_usage(
    cumulative_tokens: int,
    model: str = "sonnet",
) -> List[Advisory]:
    """Return advisories based on how full the context window is."""
    window = CONTEXT_WINDOWS.get(model, 200_000)
    pct = cumulative_tokens / window
    advisories: List[Advisory] = []

    if pct >= CLEAR_SUGGEST_PCT:
        advisories.append(Advisory(
            level="urgent",
            message=(
                f"Context is {pct*100:.0f}% full "
                f"({format_tokens(cumulative_tokens)}/{format_tokens(window)} tokens). "
                "Auto-compaction may trigger soon."
            ),
            command="/clear  (or /compact to summarize first)",
        ))
    elif pct >= COMPACT_URGENT_PCT:
        advisories.append(Advisory(
            level="warn",
            message=(
                f"Context is {pct*100:.0f}% full "
                f"({format_tokens(cumulative_tokens)}/{format_tokens(window)} tokens). "
                "Manual compaction gives better summaries than auto-compaction."
            ),
            command="/compact",
        ))
    elif pct >= COMPACT_SUGGEST_PCT:
        advisories.append(Advisory(
            level="info",
            message=(
                f"Context at {pct*100:.0f}% "
                f"({format_tokens(cumulative_tokens)}/{format_tokens(window)} tokens). "
                "Good time to compact if switching topics."
            ),
            command="/compact",
        ))

    return advisories


def build_report(
    original_tokens: int,
    compressed_tokens: int,
    strategies: List[str],
    warnings: List[str],
    cumulative_tokens: int = 0,
    model: str = "sonnet",
) -> str:
    """
    Build the stderr status line shown after each compression.
    Kept short so it doesn't clutter the terminal.
    """
    saved = original_tokens - compressed_tokens
    lines: List[str] = []

    if saved > 0:
        pct = (saved / original_tokens) * 100
        strat_str = ", ".join(strategies) if strategies else "whitespace"
        lines.append(
            f"[token-lens] {original_tokens} → {compressed_tokens} tokens "
            f"(-{saved}, -{pct:.0f}%)  [{strat_str}]"
        )
    else:
        lines.append(f"[token-lens] {original_tokens} tokens (no compression applied)")

    for w in warnings:
        lines.append(f"[token-lens] ⚠  {w}")

    if cumulative_tokens > 0:
        advisories = check_context_usage(cumulative_tokens, model)
        for adv in advisories:
            prefix = {"info": "ℹ", "warn": "⚠", "urgent": "✖"}.get(adv.level, "ℹ")
            lines.append(f"[token-lens] {prefix}  {adv.message}")
            if adv.command:
                lines.append(f"[token-lens]    → {adv.command}")

    return "\n".join(lines)
