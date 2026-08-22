# TideMind Skills

本仓库收录可供 Codex 等编码 Agent 使用的技能。

## knowledge-maintainer

维护符合 Open Knowledge Format（OKF）的仓库内 `context-kg` 知识库，支持创建、更新、查询、重组、校验、代码反向生成和渐进式加载。

### 使用 npx 安装

交互式安装：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer
```

全局安装到 Codex，并跳过确认：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer --agent codex --global --yes
```

如需安装到当前项目，移除 `--global`。安装完成后开启新的 Agent 会话，使技能被重新发现。

### 使用

在对话中直接提出知识库维护需求，或显式调用：

```text
使用 $knowledge-maintainer 更新本仓库的 context-kg，并按 OKF 格式校验。
```
