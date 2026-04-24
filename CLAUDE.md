# claude-token-lens — 项目上下文

## 项目定位

**让 context window 用得更久。** 在 prompt 提交之前、工具执行之前介入，减少 token 消耗、提升 context 寿命可见性。

这是对 Claude Code 官方 `/compact`、自动压缩、Prompt 缓存的**补充**，不是替代。官方处理事后，本工具处理事前，形成完整链路。

GitHub：https://github.com/Yaminie-Hsu/claude-token-lens

---

## 核心设计原则（不可违反）

1. **页码必须保留**：文档模块面向律师场景，页码是连接 AI 输出和原始 PDF 的唯一导航锚点。任何清洗步骤都不能删页码，只能删重复页眉页脚文字。

2. **时间线条目必须带来源**：`timeline` 输出的每条记录必须包含文件名 + 页码，否则对律师没有实用价值。

3. **零摩擦原则**：hook 是核心接入点，不能要求用户手动操作。压缩和记录必须静默发生。

4. **record_event 必须无条件调用**：每条 prompt 都要写入 DB，不能只在有压缩时才记录（曾踩过这个坑，见 hooks/user_prompt_submit.py）。

---

## 文件结构

```
claude_token_lens/
  estimator.py       # tiktoken token 计数，退化到 chars/4
  compressor.py      # 三阶段压缩：stack-trace → code-block → whitespace
  tracker.py         # SQLite 会话统计
  advisor.py         # ctx 用量建议（已废弃主动提示，仅保留逻辑备用）
  docs/
    extractor.py     # PDF/DOCX/TXT → 带 [第N页] 标记的纯文本
    cleaner.py       # 重复页眉页脚检测与去除
    chunker.py       # 按章节切割，附页码范围和 Token 数
    summarizer.py    # 目录结构 + 合同关键字段提取
    timeline.py      # 跨文档日期事件提取，输出时间线 Markdown 表格

hooks/
  user_prompt_submit.py   # UserPromptSubmit hook 入口（压缩 + 记录）
  pre_tool_use.py         # PreToolUse hook（测试失败过滤、日志截断）

cli.py              # token-lens CLI（stats / compress / setup / config / preprocess / outline / timeline）
statusline.py       # Claude Code statusLine 脚本，读取 session JSON 输出一行状态
```

---

## Statusline 格式

```
lens  8.4k↑ 2.1k↓ · ctx 15% · usage 20% · Resets in 3hr 23min · $0.0535 · saved 1.2k (14%)
```

- `↑` = input tokens，`↓` = output tokens（来自 statusLine JSON）
- `ctx %` = context window 占用率（200k，/clear 重置）
- `usage %` = 5小时速率限制消耗（与官方进度条一致）
- ctx 超 50% 变黄，超 80% 变红并追加 `· /compact or /clear`

---

## 运行测试

```bash
python3 -m pytest tests/ -q
# 预期：32 passed
```

---

## 已知局限（不要重复"修复"这些已知问题）

- `strip_code_comments` 用通用正则，可能误删行内 `//`（低优先级，已知）
- 堆栈帧检测未覆盖 Ruby/PHP/Swift/Kotlin（已知，待做）
- `advisor.py` 的 60/80/90% 提示逻辑用 DB 估算而非真实 ctx%，且仅在压缩时触发——已决定**不修复**，改用 statusline 颜色作为唯一 ctx 提醒
- PDF 扫描件（图片型）无法提取文字，需 OCR（范围外）

---

## 敏感文件说明

`/Users/viojasminie/claude-token-lens-notes/` 是**本地私有目录**，不在 git 仓库内。
内含 `handover.md`（会话交接）和 `context.md`（用户背景）。
**不要把这个目录的内容提交到 GitHub。**

---

## 当前优先待做（见 notes/roadmap.md 获取完整列表）

1. GitHub Actions CI（push 时自动跑测试）
2. 发布到 PyPI
3. 提交 awesome-claude-code 列表
