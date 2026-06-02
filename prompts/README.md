# Prompt 配置说明

本目录集中存放 Lore Seeker 的 LLM 提示词。提示词是配置，不应散落在 Agent 业务代码中。

## 规则

1. 每个提示词使用 Markdown 维护。
2. 每个可加载提示词必须放在 `<!-- prompt-id: ... -->` 和 `<!-- /prompt -->` 之间。
3. `prompt-id` 全局唯一，命名格式为 `agent.scene.role`，例如 `planner.plan.system`。
4. 需要变量替换时使用 `$variable`，由 `core.prompt_loader.render_prompt()` 渲染。
5. JSON 示例中的 `{}` 不需要转义，因为模板变量不使用 Python `str.format`。

## 核心文件

| 文件 | 内容 |
|---|---|
| `planner.md` | 任务规划和质量检查提示词 |
| `organizer.md` | Markdown 报告生成提示词 |
| `retriever.md` | 知识库问答提示词 |
