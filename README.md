# TideMind Skills

本仓库收录可供 Codex 等编码 Agent 使用的技能。详细场景、提示词和故障排查见 [Skills 使用文档](docs/README.md)。

宿主支持以实际提供的元数据为准：仓库目前只为 Codex 提供 `agents/openai.yaml`（显示名、简介与默认提示词），其他宿主请按 `npx skills` 的实际安装能力使用，不要把本仓库当作已声明支持全部宿主。变更历史见 [CHANGELOG](CHANGELOG.md)。

## Skills

| Skill | 能力 | 文档 |
| --- | --- | --- |
| `knowledge-maintainer` | 维护符合 OKF 的 `context-kg`：创建、查询、重组、校验、代码反向生成和渐进式加载 | [详细使用指南](docs/knowledge-maintainer.md) |
| `personal-development` | 开发流程、工作区协作、Go/Rust/Java 与 React 前端规范、企业 UI 可用性、正反案例与质量门禁 | [详细使用指南](docs/personal-development.md) |

## 使用 npx 安装

使用完整 GitHub 仓库 URL，交互式选择需要安装的技能：

```bash
npx skills add https://github.com/SkyMythos-ai/skills
```

只安装 `knowledge-maintainer`：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --skill knowledge-maintainer
```

全局安装到 Codex，并跳过确认：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --skill knowledge-maintainer --agent codex --global --yes
```

如需安装到当前项目，移除 `--global`。安装完成后开启新的 Agent 会话，使技能被重新发现。

`--agent` 只影响安装目标。本仓库自带的元数据仅覆盖 Codex（`skills/<name>/agents/openai.yaml`）；其他宿主能否安装与如何被发现，取决于 `npx skills` 对该宿主的实际支持，本仓库未验证的宿主不在此声明支持。

## 快速使用

在对话中直接提出知识库维护需求，或显式调用：

```text
使用 $knowledge-maintainer 更新本仓库的 context-kg，并按 OKF 格式校验。
```

更多可复制示例见 [knowledge-maintainer 使用指南](docs/knowledge-maintainer.md#典型提示词)。
