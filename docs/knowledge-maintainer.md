# knowledge-maintainer 使用指南

`knowledge-maintainer` 用于把项目中的长期知识维护为符合 Open Knowledge Format（OKF）v0.2 的 `context-kg/` Knowledge Bundle。它既能从代码、配置和测试中提炼知识，也能按渐进式加载方式查询已有知识库。

## 适用场景

| 场景 | 什么时候使用 | 典型产物 |
| --- | --- | --- |
| 初始化知识库 | 项目还没有 `context-kg/`，希望建立统一知识入口 | 根索引、领域目录、首批 concept |
| 代码反向生成 | 现有代码缺少架构、模块或接口说明 | 模块说明、接口契约、配置说明、证据来源 |
| 记录决策 | 需要沉淀架构、存储、缓存、API 或产品决策 | ADR、产品决策、相关页面链接 |
| 查询知识 | 希望 Agent 基于知识库回答架构、业务或质量问题 | 带可信度和时效性说明的回答 |
| 快速检索与增量同步 | 知识库较大，只想定位或更新真正相关的内容 | 少量候选、局部更新、可解释命中 |
| 缺陷与测试沉淀 | 修复完成后需要保留根因、回归用例或测试策略 | 缺陷复盘、测试用例、质量知识 |
| 测试与工程规范 | 需要管理测试 case、测试用例编码规则或持续生效的设计约束 | 独立 Test Case、Test Case Standard、Code Design Standard |
| 知识库治理 | 新旧方案冲突、页面重复、目录混乱、链接失效或格式不一致 | 唯一当前结论、清理后的旧内容、索引、日志和 lint 结果 |

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

增量同步从变更文件、符号、接口、业务规则和 Case ID 提取影响锚点，默认只更新目标 concept、直接关系、父索引和局部日志。正文或验证时间变化不会机械重建全库索引；删除、移动、合并、冲突治理或 taxonomy/schema 变化才扩大到全库引用检查。

当新实现或新决策与旧方案冲突时，Skill 会先区分当前事实、尚未生效的目标方案和历史决策。已经生效的新方案会替换活动页面中的旧结论；完全失效且没有审计、迁移或兼容价值的旧页面会被删除，而不是只添加一条“已废弃”提示。

### 3. 记录架构或产品决策

适合已经形成明确结论，需要长期保存背景、约束和取舍的场景。

```text
使用 $knowledge-maintainer 记录“订单查询引入 Redis 缓存”的架构决策。
包含背景、候选方案、最终选择、失效策略、风险和验证方式；
技术细节写入 technical/adr，业务页面只保留摘要与链接。
```

纯决策记录没有可跟随来源时可以省略 `sources`；不要写成 `sources: 0`。如果结论来自代码、配置、Issue 或外部规范，应记录实际 `resource`。

### 4. 快速渐进式查询已有知识

适合知识库较大、希望控制上下文并保留来源判断的场景。

```text
使用 $knowledge-maintainer 回答：订单服务为什么选择事件驱动架构？
请从 context-kg/index.md 开始渐进读取，只展开相关分支；
如果知识已过期或证据不足，再核对代码和配置。
```

读取路径是：根 `index.md` → 命中的目录 `index.md` → 带命中原因的少量候选 → 少量目标 concept → 必要的一跳链接或来源。任意层缺索引时，只会查看当前层直属项并临时合成导航，不会默认递归加载整个知识库。

精确路径、Case ID、接口名或主题词可以使用随附搜索脚本定位。默认只返回当前知识候选并排除 Session Summary；元数据无候选时优先用 `--scope` 限定正文回退范围，确需全库正文搜索时才显式增加 `--body`。中文多词跨字段检索时用空格分隔主题词：

```bash
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_search.py ./context-kg "退款幂等" --limit 5
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_search.py ./context-kg "TC-ORDER-042" --type "Test Case"
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_search.py ./context-kg "订单 幂等" --scope business
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_search.py ./context-kg "旧缓存方案" --history --body
```

候选相关性和可信度分开判断：精确 ID、标题和元数据命中负责定位，`status`、`verified`、`stale_after` 和原始来源决定能否作为当前答案。满足问题全部子意图且没有未核验冲突后立即停止，不继续预读无关分支。

### 5. 沉淀缺陷复盘和测试知识

```text
使用 $knowledge-maintainer，把这次重复扣款缺陷整理为质量知识。
记录触发条件、根因、修复原则、回归用例和仍需监控的风险；
将内容放入 quality，并链接对应业务规则和技术页面。
```

任务流水和临时排查日志不应直接变成长久知识。Skill 会提炼可复用的根因、约束和回归保护。

### 6. 管理测试用例与工程规范

```text
使用 $knowledge-maintainer 梳理订单模块的测试与工程规范知识。
把可复用测试场景分别沉淀为 Test Case，并链接需求、自动化测试和预期结果；
把测试用例编码规范与代码设计规范写入各自的权威 concept；
核对旧 case 和旧规则，合并重复项并删除已经完全失效的内容。
```

三类知识必须独立管理：

- `quality/test-cases/` 保存可独立演进的测试场景。每个 case 记录适用范围、前置条件、输入或步骤、预期结果、边界变体、覆盖状态和证据；已有自动化测试时链接其文件或测试标识，不复制代码。没有自动化的 case 明确标为 manual、planned 或 uncovered；仅有自动化映射或测试代码变更时不能写成已经验证，`verified` 需要成功执行证据。
- `quality/standards/test-case.md` 是默认的 `Test Case Standard` 入口，规定 case ID 编码、命名、粒度、必填字段、优先级、标签和自动化映射，并记录适用范围、例外与可执行检查。多个产品域或测试层级需要不同规则时，在同一目录下按范围拆分并建立索引；自动化测试代码约定确有独立生命周期时再另建 `Test Code Standard`。
- `technical/standards/code-design.md` 是默认的 `Code Design Standard` 入口，记录持续生效的模块边界、依赖方向、接口、错误处理或可扩展性约束，以及规则强度、例外和架构测试等 enforcement。一次性选型及其取舍仍写入 ADR，并与规范页互相链接。

这里的“单独文档”是每个可独立演进的范围拥有唯一权威 concept，不是把全仓库所有 case 或语言规范塞进一个巨型文件。产品规则变化时，Test Case 与自动化测试要一起核对；实现偏离已批准规范时应记录缺陷、技术债或迁移计划，不能直接把现状当成新规范。

### 7. 重组或治理知识库

```text
使用 $knowledge-maintainer 审计并重组 context-kg。
先识别同一范围内互相冲突的新旧方案并确定当前有效结论，再给出目标 taxonomy；
合并重复内容，删除已完全失效且没有历史价值的页面，隔离仍需保留的历史决策；
保持 concept ID 稳定优先，更新受影响的 index.md 和 log.md，最后运行 lint。
```

OKF 不强制固定目录分类。Skill 默认使用 `business/`、`technical/`、`quality/` 和 `tasks/`，但仓库自己的 schema 可以增加约束。删除、合并或移动页面后，Skill 还会扫描整个 `context-kg/` 的标准 Markdown 入链和 `sources[].resource`，避免索引之外留下隐性旧引用。

`status: deprecated` 只适合仍有审计、迁移或兼容价值的历史 concept，默认查询不会把它当作当前结论。它不是废弃内容的默认归宿；没有剩余价值的内容应直接移除。删除前会先把旧页中仍有效的独有内容迁移到权威页面；证据不足以判断是否仍有消费者时，Skill 会先把冲突隔离为待决事项，而不会猜测性删除。

### 8. 生成会话结束摘要

有实质决定、知识变更、验证结果、未决事项，或明确需要下次继续时，可以在本次交付前生成 Session Summary：

```text
使用 $knowledge-maintainer 收敛本次会话。
先把长期结论更新到对应权威 concept；
再生成一份简短 Session Summary，记录决定、知识变更、验证、未决项和下次检索入口。
```

默认位置是 `context-kg/tasks/session-summaries/YYYY/MM/YYYY-MM-DD-<topic>.md`，类型为 `Session Summary`。它是时间点导航快照，不是长期事实的第二权威源；普通业务查询默认排除，只在恢复工作或追溯变更脉络时读取。年、月索引按最新在前排列；不知道主题时可以直接定位最近一次摘要：

```bash
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_search.py ./context-kg --latest-session
```

如果任务页的 Review 已经完整，则直接更新 Review，不重复创建 Summary。未决项关闭且正式 concept、Review、Issue 或提交已经承接内容后，删除没有独立价值的 Summary 并清理月索引；空月、空年索引和上级入口一并清理。仅用于短期接管的工作树状态、临时命令和阻塞信息进入本地 `.handoff/`，不提交，也不作为正式知识来源。

## 预期目录

```text
context-kg/
├── index.md
├── log.md
├── business/
│   └── index.md
├── technical/
│   ├── index.md
│   ├── adr/
│   └── standards/
│       ├── index.md
│       └── code-design.md
├── quality/
│   ├── index.md
│   ├── test-cases/
│   │   └── index.md
│   └── standards/
│       ├── index.md
│       └── test-case.md
└── tasks/
    ├── index.md
    └── session-summaries/
        └── YYYY/
            └── MM/
                └── YYYY-MM-DD-topic.md
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
