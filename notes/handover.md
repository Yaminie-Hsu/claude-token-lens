# 交接文档

用于在新会话中快速恢复项目上下文。每次重要对话结束后更新。

---

## 会话 1｜2026-04-24｜项目启动 + MVP + 文档模块

### 完成内容

**Prompt 压缩模块**（`claude_token_lens/`）
- `estimator.py`：tiktoken token 计数，退化到 chars/4
- `compressor.py`：三阶段压缩（stack-trace → code-block → whitespace）
- `tracker.py`：SQLite 会话统计，记录每次压缩事件
- `advisor.py`：上下文用量建议，60/80/90% 三档提示
- `hooks/user_prompt_submit.py`：UserPromptSubmit hook 入口
- `hooks/pre_tool_use.py`：PreToolUse hook，测试命令 + 日志过滤
- `cli.py`：stats / compress / setup / config 命令

**文档处理模块**（`claude_token_lens/docs/`）
- `extractor.py`：PDF/DOCX/TXT → 带 `[第N页]` 标记的纯文本
- `cleaner.py`：重复页眉页脚检测与去除（保留页面标记）
- `chunker.py`：按章节切割，附页码范围和 Token 数
- `summarizer.py`：目录结构输出 + 合同关键字段提取
- `timeline.py`：跨文档日期事件提取，时间线 Markdown 表格

**工程**
- 32 个单元测试，全部通过
- `pyproject.toml` 打包配置
- GitHub：https://github.com/Yaminie-Hsu/claude-token-lens
- hooks 已安装到用户 `~/.claude/settings.json`

### 关键决策（详见 design.md）

1. **页码必须保留**：律师需要页码回到原文，这是文档模块最重要的设计原则
2. **补充官方功能**：定位清晰，README 有专门的对比表格
3. **时间线带来源**：每条时间节点必须有文件名 + 页码才有实用价值
4. **ISO 日期匹配**：`\b` 在中文语境下失效，用 `(?<!\d)` / `(?!\d)` 替代

### 当前状态

- 工具已在用户本地运行
- 用户正在自行测试
- 代码已推送到 GitHub
- 尚未发布到 PyPI

### 下一步

见 `roadmap.md`，优先项：
1. 用户反馈测试结果后，修复发现的问题
2. GitHub Actions CI
3. 发布 PyPI
4. 提交 awesome-claude-code

---

## 如何在新会话中恢复上下文

1. 告知 Claude：`项目在 /Users/viojasminie/claude-token-lens`
2. 让 Claude 读取 `notes/handover.md`（本文件）
3. 如需了解设计细节，读 `notes/design.md`
4. 如需了解用户场景，读 `notes/context.md`
5. 如需了解待做事项，读 `notes/roadmap.md`
