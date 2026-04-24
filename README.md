# claude-token-lens

[English](./README.md) | [中文](./README_CN.md)

> Token monitoring and smart compression for Claude Code — optimized for coding sessions.

`claude-token-lens` installs as a pair of [Claude Code hooks](https://code.claude.com/docs/en/hooks) that silently compress your prompts before they reach the API, and filter verbose tool output before Claude processes it. It also provides a CLI for session statistics and configuration.

**Works on top of every official Claude Code token-saving feature** — not instead of them.

---

## Why

Coding sessions burn tokens fast. The three biggest culprits:

| Source | Example waste |
|--------|--------------|
| Stack traces | 200-line traceback when you only need the error + 5 frames |
| Pasted code | Comment-heavy files, excessive blank lines |
| Test/log output | 10,000-line log file when you only care about `ERROR` lines |

Claude Code already provides `/compact`, `/clear`, auto-compaction, and prompt caching. `claude-token-lens` handles the part that happens *before* the prompt is submitted — so those official tools have less to work with in the first place.

---

## Features

- **`UserPromptSubmit` hook** — compresses every prompt before submission:
  - Stack trace condensation (Python, Node.js, Java, Go, Rust)
  - Code block cleanup (blank lines, optionally strip comments)
  - Whitespace normalization
- **`PreToolUse` hook** — filters Bash tool output:
  - Test runners (`pytest`, `npm test`, `go test`, …) → failures only
  - Log/file reads → last N lines
- **Session statistics** — `token-lens stats` shows cumulative savings
- **Context window advisor** — warns when context hits 60 / 80 / 90% full, suggests `/compact` or `/clear`
- **Zero config to start** — `token-lens setup` writes the hooks into `~/.claude/settings.json`
- **Configurable** — tune thresholds, enable comment stripping, adjust frame counts

---

## Quick start

```bash
# 1. Install
pip install claude-token-lens

# 2. Register hooks with Claude Code
token-lens setup

# 3. Restart Claude Code — hooks are now active
```

That's it. Every prompt you submit is now automatically compressed when savings exceed the threshold (default: 20 tokens).

---

## Installation from source

```bash
git clone https://github.com/Yaminie-Hsu/claude-token-lens.git
cd claude-token-lens
pip install -e ".[dev]"
token-lens setup
```

---

## How it works

### UserPromptSubmit hook

Claude Code calls the hook with the prompt JSON before sending to the API. The hook runs three compression passes in order:

```
prompt → [stack-trace] → [code-blocks] → [whitespace] → compressed prompt
```

**Stack trace compression** keeps the first N and last N frames, replacing the middle with a summary line:

```
Traceback (most recent call last):
  File "app.py", line 5, in <module>       ← kept (head)
    main()
  File "app.py", line 12, in main          ← kept (head)
    result = process(data)
  File "handlers/base.py", line 34, in process  ← kept (head)
    return self._dispatch(req)
    ... [7 frames omitted] ...              ← ← ← replaced
  File "utils/schema.py", line 55, in _get  ← kept (tail)
    return [f for f in self.fields ...]
  File "utils/schema.py", line 70, in _get  ← kept (tail)
    raise AttributeError("no fields defined")
AttributeError: no fields defined
```

**Code block compression** collapses consecutive blank lines inside fenced code blocks and optionally strips single-line comments.

**Whitespace normalization** collapses runs of 3+ blank lines in plain text to 2.

After compression, the hook prints a one-line report to stderr:

```
[token-lens] 562 → 517 tokens (-45, -8%)  [stack-trace, code-blocks, whitespace]
```

If compression is below the `report_threshold_tokens` (default 20), the original prompt is passed through silently.

### PreToolUse hook

Intercepts Bash commands before Claude runs them:

```bash
# Original command Claude wanted to run:
pytest tests/ -v

# Hook rewrites it to:
(pytest tests/ -v) 2>&1 | grep -A 10 -E '(FAILED|ERROR|FAIL|...)' | head -150; exit ${PIPESTATUS[0]}
```

Only failures surface in Claude's context. The exit code is preserved so Claude still knows whether tests passed.

---

## CLI reference

```bash
# Show savings report for the last 30 days (or N days)
token-lens stats
token-lens stats 7

# Compress text from stdin, print result to stdout
echo "my prompt" | token-lens compress
echo "my prompt" | token-lens compress --strip-comments

# Install hooks into ~/.claude/settings.json
token-lens setup

# Show / create the config file
token-lens config
```

---

## Configuration

After running `token-lens setup`, a config file is created at `~/.claude-token-lens/config.json`:

```json
{
  "compressor": {
    "stack_head_lines": 3,
    "stack_tail_lines": 5,
    "max_blank_lines_in_code": 1,
    "strip_code_comments": false,
    "large_code_warn_tokens": 300,
    "collapse_whitespace": true,
    "report_threshold_tokens": 20
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `stack_head_lines` | `3` | Stack frames to keep from the top |
| `stack_tail_lines` | `5` | Stack frames to keep from the bottom |
| `max_blank_lines_in_code` | `1` | Max consecutive blank lines inside code blocks |
| `strip_code_comments` | `false` | Remove `//` and `#` comment lines from code |
| `large_code_warn_tokens` | `300` | Warn when an inline code block exceeds this size |
| `collapse_whitespace` | `true` | Collapse 3+ blank lines in plain text to 2 |
| `report_threshold_tokens` | `20` | Min tokens saved before reporting |

To enable comment stripping (biggest savings for comment-heavy code):

```json
{ "compressor": { "strip_code_comments": true } }
```

---

## Relation to official Claude Code features

`claude-token-lens` is designed to complement, not replace, the token-saving tools built into Claude Code. Here is how they fit together:

| Layer | Tool | What it does |
|-------|------|-------------|
| Before prompt | **claude-token-lens** `UserPromptSubmit` | Compress the prompt you're about to send |
| Before tool | **claude-token-lens** `PreToolUse` | Filter verbose Bash output |
| During session | `/compact [instructions]` | Summarize conversation history |
| During session | `/clear` | Start fresh between unrelated tasks |
| During session | `/effort` / `MAX_THINKING_TOKENS` | Reduce extended thinking budget |
| Model choice | `/model sonnet` / `haiku` for subagents | Use cheaper models for simpler work |
| Project config | `CLAUDE.md` under 200 lines + Skills | Keep base context small |
| MCP | `/mcp` to disable unused servers | Reduce tool definition overhead |
| Monitoring | `/usage` + status line | Track context window usage |

---

## Requirements

- Python 3.9+
- Claude Code (any version with hooks support)
- `tiktoken` (installed automatically; falls back to character-based estimation if unavailable)

---

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Contributing

Issues and pull requests are welcome. Areas where contributions would be most useful:

- Additional stack trace formats (Ruby, PHP, Swift, Kotlin)
- Smarter comment detection (language-aware instead of pattern-based)
- Integration tests against real Claude Code sessions
- Windows path support in `setup` command

---

## License

MIT
