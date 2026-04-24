#!/usr/bin/env python3
"""
token-lens CLI

Commands:
  token-lens stats          Show token savings statistics
  token-lens compress       Compress text from stdin and print result
  token-lens setup          Install hooks into Claude Code settings.json
  token-lens config         Show / edit current configuration
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _cmd_stats(args: list[str]) -> None:
    from claude_token_lens.tracker import get_recent_events, get_stats
    from claude_token_lens.estimator import format_tokens, estimate_cost_usd

    days = int(args[0]) if args else 30
    stats = get_stats(days=days)

    total_saved = stats["total_saved"]
    total_original = stats["total_original"]
    avg_pct = stats["avg_pct_saved"]
    cost_saved = estimate_cost_usd(total_saved)

    print(f"\n── token-lens stats (last {days} days) ──────────────────")
    print(f"  Compression events : {stats['total_events']}")
    print(f"  Tokens submitted   : {format_tokens(total_original)}")
    print(f"  Tokens after lens  : {format_tokens(stats['total_compressed'])}")
    print(f"  Tokens saved       : {format_tokens(total_saved)}  (avg {avg_pct:.1f}% per prompt)")
    print(f"  Est. cost saved    : ${cost_saved:.4f}  (Sonnet output rate)")
    print()

    recent = get_recent_events(limit=10)
    if recent:
        print("  Recent events:")
        print(f"  {'Time':20}  {'Before':>7}  {'After':>7}  {'Saved':>7}  Strategies")
        print(f"  {'─'*20}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*20}")
        for row in recent:
            ts = row["ts"][:19].replace("T", " ")
            strat = row["strategies"] or "—"
            print(
                f"  {ts}  {row['original_tokens']:>7}  "
                f"{row['compressed_tokens']:>7}  {row['saved_tokens']:>7}  {strat}"
            )
    print()


def _cmd_compress(args: list[str]) -> None:
    from claude_token_lens.compressor import CompressorConfig, compress_prompt

    strip_comments = "--strip-comments" in args
    cfg = CompressorConfig(strip_code_comments=strip_comments)

    text = sys.stdin.read()
    result = compress_prompt(text, cfg)

    print(result.compressed, end="")
    print(
        f"\n[token-lens] {result.original_tokens} → {result.compressed_tokens} tokens "
        f"(-{result.saved}, -{result.pct_saved:.0f}%)",
        file=sys.stderr,
    )
    for w in result.warnings:
        print(f"[token-lens] ⚠  {w}", file=sys.stderr)


def _cmd_setup(args: list[str]) -> None:
    """Install hooks into ~/.claude/settings.json."""
    import os

    hook_dir = Path(__file__).parent / "hooks"
    settings_path = Path(os.environ.get("CLAUDE_SETTINGS", "~/.claude/settings.json")).expanduser()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings: dict = {}
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: could not parse {settings_path}, creating fresh.", file=sys.stderr)

    hooks = settings.setdefault("hooks", {})

    # UserPromptSubmit hook
    prompt_hook_cmd = f"python3 {hook_dir / 'user_prompt_submit.py'}"
    prompt_hooks = hooks.setdefault("UserPromptSubmit", [])
    existing_cmds = [h.get("command") for entry in prompt_hooks for h in entry.get("hooks", [])]
    if prompt_hook_cmd not in existing_cmds:
        prompt_hooks.append({"hooks": [{"type": "command", "command": prompt_hook_cmd}]})
        print(f"✓ Registered UserPromptSubmit hook")
    else:
        print(f"✓ UserPromptSubmit hook already registered")

    # PreToolUse hook (Bash only)
    tool_hook_cmd = f"python3 {hook_dir / 'pre_tool_use.py'}"
    tool_hooks = hooks.setdefault("PreToolUse", [])
    existing_cmds = [h.get("command") for entry in tool_hooks for h in entry.get("hooks", [])]
    if tool_hook_cmd not in existing_cmds:
        tool_hooks.append({
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": tool_hook_cmd}],
        })
        print(f"✓ Registered PreToolUse hook (Bash)")
    else:
        print(f"✓ PreToolUse hook already registered")

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    print(f"\nSettings written to {settings_path}")
    print("Restart Claude Code for changes to take effect.\n")


def _cmd_config(args: list[str]) -> None:
    import os
    from claude_token_lens.tracker import DATA_DIR

    config_path = DATA_DIR / "config.json"

    if not config_path.exists():
        default = {
            "compressor": {
                "stack_head_lines": 3,
                "stack_tail_lines": 5,
                "max_blank_lines_in_code": 1,
                "strip_code_comments": False,
                "large_code_warn_tokens": 300,
                "collapse_whitespace": True,
                "report_threshold_tokens": 20,
            }
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(default, f, indent=2)
            f.write("\n")
        print(f"Created default config at {config_path}")

    print(f"\nConfig file: {config_path}\n")
    with open(config_path) as f:
        print(f.read())


COMMANDS = {
    "stats":    _cmd_stats,
    "compress": _cmd_compress,
    "setup":    _cmd_setup,
    "config":   _cmd_config,
}

HELP = """\
Usage: token-lens <command> [options]

Commands:
  stats [days]    Token savings report (default: last 30 days)
  compress        Compress stdin prompt, print result to stdout
    --strip-comments   Also remove single-line code comments
  setup           Install hooks into ~/.claude/settings.json
  config          Show / create config file

Examples:
  token-lens stats
  token-lens stats 7
  echo "my prompt" | token-lens compress
  token-lens setup
"""


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(HELP)
        return

    cmd_name = argv[0]
    cmd_args = argv[1:]

    if cmd_name not in COMMANDS:
        print(f"Unknown command: {cmd_name}\n", file=sys.stderr)
        print(HELP)
        sys.exit(1)

    COMMANDS[cmd_name](cmd_args)


if __name__ == "__main__":
    main()
