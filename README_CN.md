# claude-token-lens

[English](./README.md) | [中文](./README_CN.md)

> Claude Code 的 Token 监控与智能压缩工具 — 专为编程与文档分析场景优化

`claude-token-lens` 以一对 [Claude Code Hooks](https://code.claude.com/docs/en/hooks) 的形式运行，在 Prompt 发送到 API 之前自动完成压缩，并在工具执行前过滤冗余输出。同时提供 CLI 工具，用于查看会话统计和进行文档预处理。

**构建在所有 Claude Code 官方节省 Token 功能之上** — 与官方工具互补，而非替代。

---

## 为什么需要它

编程会话消耗 Token 极快，主要来自三个来源：

| 来源 | 典型浪费 |
|------|---------|
| 错误堆栈 | 200 行报错，实际只需要错误信息 + 5 帧 |
| 粘贴代码 | 注释密集的文件、大量多余空行 |
| 测试/日志输出 | 一万行日志，你只关心 `ERROR` 行 |

Claude Code 已经提供了 `/compact`、`/clear`、自动压缩和 Prompt 缓存。`claude-token-lens` 负责更早的环节——在 Prompt 提交之前就完成处理，让那些官方工具面对的内容更少。

---

## 功能一览

**编程场景（Prompt 压缩）**
- **`UserPromptSubmit` hook** — 每次提交前自动压缩：
  - 堆栈帧浓缩（支持 Python、Node.js、Java、Go、Rust）
  - 代码块清理（合并多余空行，可选去注释）
  - 空白符规范化
- **`PreToolUse` hook** — 过滤 Bash 工具输出：
  - 测试命令（`pytest`、`npm test`、`go test` 等）→ 只返回失败项
  - 日志/文件读取 → 截取最后 N 行
- **会话统计** — `token-lens stats` 查看累计节省
- **上下文用量提醒** — 达到 60 / 80 / 90% 时提示 `/compact` 或 `/clear`

**文档分析场景（法律、研究、合同）**
- **`token-lens preprocess`** — PDF/DOCX 提取为带 `[第N页]` 标记的纯文本，去除重复页眉页脚，**页码标记完整保留**
- **`token-lens outline`** — 输出文档目录结构，每个章节注明页码和 Token 数，便于按需取用
- **`token-lens timeline`** — 跨多份文档提取日期事件，按时间顺序排列，每条记录标注来源文件和页码

---

## 快速开始

```bash
# 1. 安装
pip install claude-token-lens

# 2. 注册 hooks
token-lens setup

# 3. 重启 Claude Code — hooks 立即生效
```

完成。此后每次提交的 Prompt 都会自动压缩，节省超过阈值（默认 20 tokens）时会在终端打印报告：

```
[token-lens] 562 → 517 tokens (-45, -8%)  [stack-trace, code-blocks, whitespace]
```

---

## 从源码安装

```bash
git clone https://github.com/Yaminie-Hsu/claude-token-lens.git
cd claude-token-lens
pip install -e ".[dev]"
token-lens setup
```

---

## 工作原理

### UserPromptSubmit hook（Prompt 压缩）

Claude Code 在将 Prompt 发送到 API 之前调用此 hook，依次执行三个压缩步骤：

```
prompt → [stack-trace] → [code-blocks] → [whitespace] → compressed prompt
```

**堆栈帧压缩** 保留头部 N 帧和尾部 N 帧，中间部分替换为摘要行：

```
Traceback (most recent call last):
  File "app.py", line 5, in <module>            ← 保留（头部）
    main()
  File "app.py", line 12, in main               ← 保留（头部）
    result = process(data)
  File "handlers/base.py", line 34, in process  ← 保留（头部）
    return self._dispatch(req)
    ... [7 frames omitted] ...                  ← 替换
  File "utils/schema.py", line 55, in _get      ← 保留（尾部）
    return [f for f in self.fields ...]
  File "utils/schema.py", line 70, in _get      ← 保留（尾部）
    raise AttributeError("no fields defined")
AttributeError: no fields defined
```

**代码块压缩** 合并 fenced code block 内的连续空行，可选去除单行注释。

**空白符规范化** 将正文中连续 3 行以上的空行压缩为 2 行。

### PreToolUse hook（工具输出过滤）

拦截 Bash 命令，在执行前重写：

```bash
# Claude 原本要执行的命令：
pytest tests/ -v

# Hook 重写后：
(pytest tests/ -v) 2>&1 | grep -A 10 -E '(FAILED|ERROR|FAIL|...)' | head -150; exit ${PIPESTATUS[0]}
```

只有失败项进入 Claude 的上下文，退出码保留，Claude 仍能判断测试是否通过。

### 文档处理（法律 / 研究场景）

#### token-lens preprocess

提取文档为纯文本，在每页边界插入页面标记：

```
─── [第 12 页] ────────────────────────────────────────
第八条　违约责任
若乙方未能按期交付，应向甲方支付合同总额百分之五的违约金……

─── [第 13 页] ────────────────────────────────────────
……双方协商一致可予以延期，延期不超过三十个自然日。
```

> **为什么保留页码？**
> AI 分析后给出引用片段，律师或研究人员需要凭借页码回到原始 PDF 核实原文。去掉页码等于切断了 AI 输出与原文之间的唯一索引。

同时自动识别并去除重复的页眉页脚（如"保密文件 XX公司 2024"），但页面标记始终保留。

#### token-lens outline

输出文档目录，每个章节注明页码和 Token 数：

```
## 文档目录

章节标题                                   页码         Tokens
────────────────────────────────────────────────────────────────
第一条　总则                               第 1 页          142
第二条　定义                               第 2–3 页        315
第三条　权利义务                           第 4–6 页        489
...
────────────────────────────────────────────────────────────────
合计                                                       3,241
```

拿到这份目录后，只需把需要分析的章节内容喂给 Claude，而不是整份文档。

#### token-lens timeline

跨多份文档提取时间线，按日期排序，每条记录标注来源和页码：

```
## 事件时间线

| 日期         | 事件摘要                          | 来源文件         | 页码    |
|-------------|----------------------------------|----------------|--------|
| 2023-03-01  | 甲乙双方签署《框架合作协议》          | 框架协议.pdf     | 第 3 页 |
| 2023-06-15  | 乙方提交首期交付物                  | 往来函件.pdf     | 第 7 页 |
| 2023-09-30  | 甲方发出验收意见                    | 往来函件.pdf     | 第 9 页 |
| 2024-01-10  | 甲方发出违约通知函                  | 通知函.pdf       | 第 1 页 |
```

支持日期格式：`2024年3月15日`、`2024-03-15`、`2024/03/15`、`March 15, 2024` 等。

---

## CLI 参考

```bash
# ── Prompt 压缩 ──────────────────────────────────────────
# 查看 Token 节省报告（默认最近 30 天）
token-lens stats
token-lens stats 7

# 压缩 stdin 输入的文本
echo "my prompt" | token-lens compress
echo "my prompt" | token-lens compress --strip-comments

# 安装 hooks 到 ~/.claude/settings.json
token-lens setup

# 查看 / 创建配置文件
token-lens config

# ── 文档处理 ─────────────────────────────────────────────
# 清洗文档，输出带页面标记的纯文本
token-lens preprocess contract.pdf > contract_clean.txt
token-lens preprocess contract.pdf --keep-headers  # 保留页眉页脚

# 查看文档目录结构
token-lens outline contract.pdf

# 跨文档生成时间线
token-lens timeline contract.pdf emails.pdf notice.pdf
```

---

## 配置

运行 `token-lens setup` 后，配置文件创建于 `~/.claude-token-lens/config.json`：

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

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `stack_head_lines` | `3` | 保留堆栈头部帧数 |
| `stack_tail_lines` | `5` | 保留堆栈尾部帧数 |
| `max_blank_lines_in_code` | `1` | 代码块内最多连续空行数 |
| `strip_code_comments` | `false` | 去除 `//` 和 `#` 单行注释 |
| `large_code_warn_tokens` | `300` | 超过此大小的代码块触发警告 |
| `collapse_whitespace` | `true` | 正文中 3 行以上空行压缩为 2 行 |
| `report_threshold_tokens` | `20` | 节省低于此值时静默处理 |

注释密集的代码建议开启：

```json
{ "compressor": { "strip_code_comments": true } }
```

---

## 与 Claude Code 官方功能的关系

`claude-token-lens` 定位为**补充**，而非替代官方工具：

| 层级 | 工具 | 作用 |
|------|------|------|
| Prompt 提交前 | **claude-token-lens** `UserPromptSubmit` | 压缩即将发送的 Prompt |
| 工具执行前 | **claude-token-lens** `PreToolUse` | 过滤冗余 Bash 输出 |
| 会话中 | `/compact [指令]` | 压缩对话历史 |
| 会话中 | `/clear` | 切换任务时清空上下文 |
| 会话中 | `/effort` / `MAX_THINKING_TOKENS` | 降低 extended thinking 预算 |
| 模型选择 | `/model sonnet` / subagent 用 `haiku` | 简单任务用更便宜的模型 |
| 项目配置 | `CLAUDE.md` 控制在 200 行内 + Skills | 减小基础上下文 |
| MCP | `/mcp` 禁用不用的 server | 减少工具定义占用 |
| 监控 | `/usage` + 状态栏 | 实时查看上下文用量 |

---

## 环境要求

- Python 3.9+
- Claude Code（任何支持 hooks 的版本）
- `tiktoken`（自动安装；不可用时退化为字符数估算）
- `pypdf`（文档功能需要，`pip install pypdf`）
- `python-docx`（Word 文档支持，`pip install python-docx`）

---

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 参与贡献

欢迎提 Issue 和 Pull Request。以下方向贡献价值最大：

- 支持更多堆栈格式（Ruby、PHP、Swift、Kotlin）
- 更智能的注释检测（语言感知，而非通用正则）
- 针对真实 Claude Code 会话的集成测试
- Windows 路径支持（`setup` 命令）

---

## 许可证

MIT
