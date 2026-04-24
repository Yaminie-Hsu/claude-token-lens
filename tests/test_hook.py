"""Tests for the UserPromptSubmit hook I/O contract."""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "user_prompt_submit.py"


def _run_hook(event: dict) -> tuple[dict, str]:
    """Run the hook with the given event, return (stdout_json, stderr_str)."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    output = json.loads(stdout) if stdout else {}
    return output, result.stderr


def test_empty_prompt_passes_through():
    output, _ = _run_hook({"prompt": "", "session_id": "test"})
    assert output == {}


def test_invalid_json_passes_through():
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "{}"


def test_plain_prompt_no_modification():
    output, _ = _run_hook({"prompt": "What is a linked list?", "session_id": "test"})
    # Short plain prompt should not be modified
    assert output == {} or "updatedPrompt" not in output.get("hookSpecificOutput", {})


def test_compressible_prompt_returns_updated():
    big_trace = (
        "Traceback (most recent call last):\n"
        + "  File 'x.py', line {i}, in fn\n    do_thing()\n" * 12
        + "ValueError: bad\n"
    )
    event = {
        "prompt": f"I got this error:\n{big_trace}\nHow do I fix it?",
        "session_id": "test",
        "cwd": "/tmp",
    }
    output, stderr = _run_hook(event)
    if output:
        assert "hookSpecificOutput" in output
        assert "updatedPrompt" in output["hookSpecificOutput"]
        updated = output["hookSpecificOutput"]["updatedPrompt"]
        assert "frames omitted" in updated
