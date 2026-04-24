"""Token estimation using tiktoken (cl100k_base ≈ Claude tokenization)."""

from __future__ import annotations

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

    TIKTOKEN_AVAILABLE = True

except ImportError:
    # Fallback: ~4 chars per token (conservative estimate)
    def count_tokens(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text) // 4)

    TIKTOKEN_AVAILABLE = False


def format_tokens(n: int) -> str:
    """Human-readable token count."""
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def estimate_cost_usd(tokens: int, model: str = "sonnet") -> float:
    """Rough cost estimate (output tokens, per-token pricing as of 2026)."""
    rates = {
        "haiku":  3e-6,
        "sonnet": 15e-6,
        "opus":   75e-6,
    }
    rate = rates.get(model, rates["sonnet"])
    return tokens * rate
