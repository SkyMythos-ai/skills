# knowledge-maintainer 使用指南

`knowledge-maintainer` 用于把项目中的长期知识维护为符合 Open Knowledge Format（OKF）v0.2 的 `context-kg/` Knowledge Bundle。它既能从代码、配置和测试中提炼知识，也能按渐进式加载方式查询已有知识库。

## 适用场景

| 场景 | 什么时候使用 | 典型产物 |
| --- | --- | --- |
| 初始化知识库 | 项目还没有 `context-kg/`，希望建立统一知识入口 | 根索引、领域目录、首批 concept |
| 代码反向生成 | 现有代码缺少架构、模块或接口说明 | 模块说明、接口契约、配置说明、证据来源 |
| 记录决策 | 需要沉淀架构、存储、缓存、API 或产品决策 | ADR、产品决策、相关页面链接 |
| 查询知识 | 希望 Agent 基于知识库回答架构、业务或质量问题 | 带可信度和时效性说明的回答 |
| 缺陷与测试沉淀 | 修复完成后需要保留根因、回归用例或测试策略 | 缺陷复盘、测试用例、质量知识 |
| 知识库治理 | 页面重复、目录混乱、链接失效或格式不一致 | 重组后的目录、索引、日志和 lint 结果 |

以下情况通常不需要使用：只改一行临时代码且没有可复用知识、仅记录短期聊天过程、或者只想创建普通用户文档而不维护 `context-kg/`。

## 安装

交互式安装：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer
```

全局安装到 Codex，并跳过确认：

```bash
npx skills add TideMind/skills --skill knowledge-maintainer --agent codex --global --yes
```

项目级安装时移除 `--global`。安装后开启新的 Agent 会话，使 Skill 被重新发现。

可以先查看仓库中可安装的 Skill：

```bash
npx skills add TideMind/skills --list
```

## 快速开始

显式调用 Skill 最容易得到稳定行为：

```text
使用 $knowledge-maintainer 初始化本仓库的 context-kg。
先从代码、配置和测试收集证据，再建立符合 OKF v0.2 的索引与核心页面。
```

如果知识库已经存在：

```text
使用 $knowledge-maintainer，把最近完成的缓存改造沉淀到 context-kg。
更新相关 ADR、标准 Markdown 链接、分层 index.md 和 log.md，并运行 lint。
```

## 典型用法

### 1. 从代码建立或补全知识库

适合接手老项目、补架构文档或完成大模块后回填知识。

```text
使用 $knowledge-maintainer，从当前代码库反向生成知识。
重点梳理服务入口、模块边界、公开 API、配置、数据模型和测试策略。
只写有代码或测试证据支持的事实，并在每个 concept 中记录 sources。
```

Skill 会优先读取已有索引，避免生成重复页面；随后从入口、公开 API、配置、schema 和测试中建立证据链。代码事实与产品意图会被区分，不确定内容不会被包装成结论。

### 2. 代码变更后同步长期知识

适合功能、接口、数据模型或部署方式发生变化后，只更新真正受影响的知识。

```text
使用 $knowledge-maintainer 审查当前分支相对 main 的改动。
识别受影响的业务、技术和质量知识，只更新需要变化的 concept；
同步相关 index.md 和 log.md，并用代码、配置或测试记录真实 sources。
```

Skill 不会把提交记录原样复制进知识库，而会提炼稳定的职责、边界、行为和决策。纯重构且对外行为与长期知识均未变化时，可以不修改 concept。

### 3. 记录架构或产品决策

适合已经形成明确结论，需要长期保存背景、约束和取舍的场景。

```text
使用 $knowledge-maintainer 记录“订单查询引入 Redis 缓存”的架构决策。
包含背景、候选方案、最终选择、失效策略、风险和验证方式；
技术细节写入 technical/adr，业务页面只保留摘要与链接。
```

纯决策记录没有可跟随来源时可以省略 `sources`；不要写成 `sources: 0`。如果结论来自代码、配置、Issue 或外部规范，应记录实际 `resource`。

### 4. 渐进式查询已有知识

适合知识库较大、希望控制上下文并保留来源判断的场景。

```text
使用 $knowledge-maintainer 回答：订单服务为什么选择事件驱动架构？
请从 context-kg/index.md 开始渐进读取，只展开相关分支；
如果知识已过期或证据不足，再核对代码和配置。
```

读取路径是：根 `index.md` → 命中的目录 `index.md` → 少量目标 concept → 必要的链接或来源。任意层缺索引时，只会查看当前层直属项并临时合成导航，不会默认递归加载整个知识库。

### 5. 沉淀缺陷复盘和测试知识

```text
使用 $knowledge-maintainer，把这次重复扣款缺陷整理为质量知识。
记录触发条件、根因、修复原则、回归用例和仍需监控的风险；
将内容放入 quality，并链接对应业务规则和技术页面。
```

任务流水和临时排查日志不应直接变成长久知识。Skill 会提炼可复用的根因、约束和回归保护。

### 6. 重组或治理知识库

```text
使用 $knowledge-maintainer 审计并重组 context-kg。
先给出目标 taxonomy，再处理重复页面、错误目录和断链；
保持 concept ID 稳定优先，更新受影响的 index.md 和 log.md，最后运行 lint。
```

OKF 不强制固定目录分类。Skill 默认使用 `business/`、`technical/`、`quality/` 和 `tasks/`，但仓库自己的 schema 可以增加约束。

## 预期目录

```text
context-kg/
├── index.md
├── log.md
├── business/
│   └── index.md
├── technical/
│   ├── index.md
│   └── adr/
├── quality/
│   └── index.md
└── tasks/
    └── index.md
```

目录可以按项目调整。OKF 的关键要求是：普通 Markdown concept 有可解析的 YAML frontmatter 和非空 `type`；`index.md`、`log.md` 使用各自的保留格式；concept 间使用标准 Markdown 链接。

## 校验

安装 Skill 后，在目标项目根目录运行：

```bash
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_lint.py ./context-kg
```

项目级安装时，将脚本路径替换为实际安装位置。lint 会把格式错误标为 `✗`，把 OKF 允许但会降低维护质量的情况标为 `⚠`，例如断链或推荐索引缺失。

建议同时运行仓库自身的测试，以及：

```bash
git diff --check
git status --short --untracked-files=all
```

## 常见问题

### 安装后无法调用

先开启新的 Agent 会话，再检查 Skill 是否被正确发现：

```bash
npx skills add TideMind/skills --list
```

确认安装时选择了当前使用的 Agent；Codex 的 agent 标识是 `codex`。

### lint 提示缺少 PyYAML

校验脚本需要 Python 3 和 PyYAML。可以在合适的 Python 环境中安装：

```bash
python3 -m pip install pyyaml
```

### 断链为什么只是警告

OKF 消费者需要容忍尚未补齐的链接，因此断链不会使 bundle 本身不合规。维护时仍应修复可确认的断链，避免渐进式导航失效。

### `context-kg` 和普通 `docs/` 有什么区别

`context-kg/` 面向 Agent 和人共同消费，强调类型、来源、链接、可信度、生命周期和渐进式导航。普通 `docs/` 更适合安装指南、用户教程和发布说明。长期架构与业务知识应进入 `context-kg/`，本 Skill 的使用说明则放在本仓库的 `docs/`。

## 相关资源

- [仓库首页](../README.md)
- [Skills 文档索引](README.md)
- [Skill 执行规范](../skills/knowledge-maintainer/SKILL.md)
- [OKF v0.2 规范](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)
