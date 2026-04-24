# 路线图与待完善项

## 已完成（v0.1.0）

### Prompt 压缩
- [x] `UserPromptSubmit` hook：stack-trace / code-block / whitespace 压缩
- [x] `PreToolUse` hook：测试命令失败过滤、日志截断
- [x] SQLite 会话统计
- [x] 上下文用量建议（60% / 80% / 90% 阈值）
- [x] `token-lens stats / compress / setup / config` CLI
- [x] `pyproject.toml` 打包配置

### 文档处理
- [x] PDF / DOCX / TXT 提取，带 `[第N页]` 页面标记
- [x] 重复页眉页脚检测与去除
- [x] 按章节切割，附页码范围
- [x] 目录结构输出（outline）
- [x] 跨文档时间线提取（中文 / ISO / 英文日期格式）
- [x] 合同关键字段提取（甲乙方、金额、日期、管辖等）
- [x] `token-lens preprocess / outline / timeline` CLI

### 工程
- [x] 32 个单元测试，全部通过
- [x] 英文 README + 中文 README
- [x] `notes/` 设计文档

---

## 近期待完善（v0.2）

### 质量提升
- [ ] 注释检测改为语言感知（现在是通用正则，可能误删）
- [ ] 堆栈帧检测补充 Ruby、PHP、Swift、Kotlin
- [ ] Windows 路径支持（`setup` 命令）
- [ ] `timeline` 对相对日期的处理（"本月"、"当日"等）

### 文档处理增强
- [ ] 表格提取：PDF 中的表格内容（条款表、金额明细）
- [ ] 合同摘要模板：生成标准化的合同摘要卡片
- [ ] 批量处理：`token-lens preprocess *.pdf` 批量清洗目录下所有文件
- [ ] 智能分段建议：根据 Token 数建议"先喂第几章"

### 工程
- [ ] 发布到 PyPI（`pip install claude-token-lens` 真正可用）
- [ ] GitHub Actions CI（push 时自动跑测试）
- [ ] 提交到 `awesome-claude-code` 列表

---

## 中期方向（v0.3+）

- [ ] 交互式 outline：`token-lens outline` 后可选择要分析的章节，直接输出该章节内容
- [ ] 会话报告：每次 `/clear` 后自动生成本次会话的 Token 使用摘要
- [ ] 多语言文档支持（英文合同的关键字段提取）
- [ ] 与 Claude Code subagent 集成：自动为每份文档分配独立 subagent

---

## 已知问题

| 问题 | 严重程度 | 状态 |
|------|---------|------|
| `strip_code_comments` 可能误删行内 URL 中的 `//` | 低 | 待修 |
| 超短文档（< 3 页）不做页眉页脚检测 | 低 | 已知，设计如此 |
| PDF 扫描件（图片型）无法提取文字 | 中 | 需引入 OCR（范围外） |
| DOCX 页码检测依赖 `lastRenderedPageBreak`，部分 Word 版本可能缺失 | 中 | 待调研 |
