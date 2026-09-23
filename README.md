# TideMind Skills

本仓库收录可供 Codex 等编码 Agent 使用的技能。详细场景、提示词和故障排查见 [Skills 使用文档](docs/README.md)。

## Skills

| Skill | 能力 | 文档 |
| --- | --- | --- |
| `knowledge-maintainer` | 维护符合 OKF 的 `context-kg`：创建、查询、重组、校验、代码反向生成和渐进式加载 | [详细使用指南](docs/knowledge-maintainer.md) |
| `personal-coding-style` | 个人编码规范、Go/Rust/Java 惯用法、正反案例与质量门禁 | [详细使用指南](docs/personal-coding-style.md) |

## 使用 npx 安装

交互式安装：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer
```

全局安装到 Codex，并跳过确认：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer --agent codex --global --yes
```

如需安装到当前项目，移除 `--global`。安装完成后开启新的 Agent 会话，使技能被重新发现。

## 快速使用

在对话中直接提出知识库维护需求，或显式调用：

```text
使用 $knowledge-maintainer 更新本仓库的 context-kg，并按 OKF 格式校验。
```

更多可复制示例见 [knowledge-maintainer 使用指南](docs/knowledge-maintainer.md#典型用法)。
