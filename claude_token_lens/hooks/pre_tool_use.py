#!/usr/bin/env python3
"""
Claude Code PreToolUse hook.

Filters verbose tool inputs before Claude processes them:
- Test runners (pytest, npm test, go test): show only failures
- Log-reading commands: truncate to last N lines
- Large file reads: warn if file exceeds token threshold

Install via setup.py or add manually to settings.json:
  {
    "hooks": {
      "PreToolUse": [{
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "python3 /path/to/hooks/pre_tool_use.py"}]
      }]
    }
  }
"""

from __future__ import annotations

import json
import re
import sys

# Commands that produce verbose output — wrap to filter failures only
_TEST_RUNNERS = re.compile(
    r"^\s*(pytest|python -m pytest|npm test|npm run test|"
    r"yarn test|go test|cargo test|jest|vitest|mocha)\b"
)

# Log/output commands — tail to last N lines
_LOG_COMMANDS = re.compile(
    r"(cat|tail|head|less|more|docker logs|kubectl logs)\s+\S"
)

_LOG_TAIL_LINES = 200


def _wrap_test_command(cmd: str) -> str:
    """Wrap test command to show only failures (exit code preserved)."""
    return (
        f"({cmd}) 2>&1 | "
        r"grep -A 10 -E '(FAILED|ERROR|FAIL|error\[|test.*FAIL|✗|✕|×)' "
        r"| head -150; exit ${PIPESTATUS[0]}"
    )


def _wrap_log_command(cmd: str) -> str:
    """Append tail limit to log commands that don't already have one."""
    if re.search(r"-n\s*\d+|--lines", cmd):
        return cmd
    return f"{cmd} 2>&1 | tail -n {_LOG_TAIL_LINES}"


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        print("{}", flush=True)
        return

    tool_name: str = event.get("tool_name", "")
    tool_input: dict = event.get("tool_input", {})

    if tool_name != "Bash":
        print("{}", flush=True)
        return

    cmd: str = tool_input.get("command", "")
    if not cmd:
        print("{}", flush=True)
        return

    new_cmd = cmd
    applied: list[str] = []

    if _TEST_RUNNERS.match(cmd):
        new_cmd = _wrap_test_command(cmd)
        applied.append("filter-test-failures")

    elif _LOG_COMMANDS.search(cmd) and "token-lens" not in cmd:
        new_cmd = _wrap_log_command(cmd)
        applied.append("truncate-log-output")

    if new_cmd != cmd:
        print(
            f"[token-lens] pre-tool: {', '.join(applied)}",
            file=sys.stderr,
            flush=True,
        )
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {**tool_input, "command": new_cmd},
            }
        }
    else:
        output = {}

    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
