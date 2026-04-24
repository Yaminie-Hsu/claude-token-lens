# 项目背景与用户场景

## 项目起源

由开发者 Yaminie Hsu 发起，核心动机：

1. **个人使用**：写代码时 Token 消耗过快，需要一个自动化的节省工具
2. **开源影响力**：希望发布到 GitHub，目标是获得 Claude/Anthropic 官方推荐
3. **职业认可**：这也是对自身技术能力的一种公开展示

---

## 主要用户场景

### 场景 A：开发者（核心场景）

**特征**：
- 频繁粘贴错误报错、代码片段
- 同一会话内上下文积累快
- 关心 Token 消耗但不想手动管理

**痛点**：
- 粘贴 200 行报错只需要 10 行
- 代码里的注释和空行也在计费
- 不知道当前 session 用了多少 Token

**工具响应**：
- `UserPromptSubmit` hook 自动压缩
- `PreToolUse` hook 过滤测试输出
- `token-lens stats` 查看累计节省

---

### 场景 B：律师 / 法律工作者（文档场景）

**特征**：
- Claude Max 用户，仍会用超
- 需要读入大量 PDF 合同、函件、法庭文书
- 分析后必须回到原文核实，页码是关键导航信息

**痛点**：
- 直接喂整份文档 = 大量 Token 付费"读废话"
- 解析平台输出的 Markdown 丢失页面边界信息
- AI 给出引用片段后找不到对应原文位置
- 多份文件的时间线需要手动梳理，极耗时

**核心洞察**（用户直接反馈）：
> "解析平台返回的是 Markdown 文本，但没有页码信息——Markdown 里的内容是连续的，页面边界丢失了。所以假如 AI 返回了引用片段，在律师阅卷场景里，也不知道它在原始 PDF 的第几页。"

**工具响应**：
- `token-lens preprocess`：提取 PDF 并**在每页插入页面标记**，自动去除重复页眉页脚
- `token-lens outline`：先看目录结构再决定喂哪几章，避免整文档喂入
- `token-lens timeline`：跨文档时间线，每条记录带来源文件和页码

---

### 场景 C：研究人员 / 文档密集型用户

与律师场景类似，使用 preprocess + outline + timeline 三个命令。

---

## 官方推荐策略

为提升被 Anthropic 官方注意到的概率，做了以下定位：

1. **明确定位为"补充"**：README 有专门的表格说明与官方功能的分工，不声称替代
2. **原生集成**：使用官方 hook 系统，而非另起炉灶
3. **Topics 标签**：`claude-code`、`anthropic`、`llm`、`token-optimization`、`developer-tools`、`hooks`
4. **下一步**：提交到 `awesome-claude-code` 列表，发到 Anthropic Discord `#claude-code` 频道
