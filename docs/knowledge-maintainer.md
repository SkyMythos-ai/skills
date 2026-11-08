# knowledge-maintainer 使用指南

`knowledge-maintainer` 把项目中的长期知识维护为符合 Open Knowledge Format（OKF）v0.2 的 `context-kg/` Knowledge Bundle：既能从代码、配置和测试中提炼知识，也能按渐进式加载方式查询已有知识库。

本页只讲怎么用：适用与不适用、安装、典型提示词、预期目录、校验与排错。执行规范、页面契约和治理流程在 Skill 正文与 references 中维护，本页不复述，避免同一规则出现两版。

## 路径约定

下文命令统一用 `$SKILL_DIR` 代表 Skill 的实际安装目录，先设置再复制运行：

```bash
# 按自己的安装位置填写，不要写死某个宿主的目录
export SKILL_DIR=/path/to/knowledge-maintainer
```

- 仓库内形态：脚本在 `skills/knowledge-maintainer/scripts/`，可以从仓库根目录直接运行，例如 `python3 skills/knowledge-maintainer/scripts/context_kg_lint.py ./context-kg`。
- 已安装形态：脚本在安装目录的 `scripts/` 下，命令统一写作 `python3 "$SKILL_DIR/scripts/<name>.py"`。
- 本页不依赖固定宿主安装位置：换 Agent、换安装范围或直接把仓库当 Skill 用时，只改 `$SKILL_DIR`；`docs/personal-development.md` 采用同样写法。

Codex 全局安装时，`SKILL_DIR` 取 `~/.codex/skills/knowledge-maintainer`（仅在说明中出现，可复制的命令一律使用 `$SKILL_DIR`）。

## 适用场景

先判断不适用的情况：只改一行临时代码且没有可复用知识、仅记录短期聊天过程、只想创建普通用户文档而不维护 `context-kg/`、纯代码实现与重构、以及构建或镜像语境中的 `rebuild`。该范围与 [Skill 触发范围](../skills/knowledge-maintainer/SKILL.md) 的 `description` 一致，是否触发的判定以 SKILL.md 为准；本页只列使用场景。

| 场景 | 什么时候使用 | 典型产物 |
| --- | --- | --- |
| 初始化知识库 | 项目还没有 `context-kg/`，希望建立统一知识入口 | 根索引、领域目录、首批 concept |
| 代码反向生成 | 现有代码缺少架构、模块或接口说明 | 模块说明、接口契约、配置说明、证据来源 |
| 记录决策 | 需要沉淀架构、存储、缓存、API 或产品决策 | ADR、产品决策、相关页面链接 |
| 查询知识 | 希望 Agent 基于知识库回答架构、业务或质量问题 | 带可信度和时效性说明的回答 |
| 快速检索与增量同步 | 知识库较大，只想定位或更新真正相关的内容 | 少量候选、局部更新、可解释命中 |
| 缺陷与测试沉淀 | 修复完成后需要保留根因、回归用例或测试策略 | 缺陷复盘、测试用例、质量知识 |
| 测试与工程规范 | 需要管理测试 case、测试用例编码规则或持续生效的设计约束 | 独立 Test Case、Test Case Standard、Code Design Standard |
| 全库知识治理 | 分类混杂、命名含糊、需求变更、历史混入当前知识或重复页面 | 盘点与命名诊断、有效性证据、可检查计划、归档与恢复记录 |

## 安装

通过完整 GitHub 仓库 URL，交互式安装指定技能：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --skill knowledge-maintainer
```

全局安装到 Codex，并跳过确认：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --skill knowledge-maintainer --agent codex --global --yes
```

项目级安装时移除 `--global`。安装后开启新的 Agent 会话，使 Skill 被重新发现。可以先查看仓库中可安装的 Skill：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --list
```

## 典型提示词

初始化：

```text
使用 $knowledge-maintainer 初始化本仓库的 context-kg。
先从代码、配置和测试收集证据，再建立符合 OKF v0.2 的索引与核心页面。
```

代码反向生成或增量同步：

```text
使用 $knowledge-maintainer，从当前代码库反向生成知识。
重点梳理服务入口、模块边界、公开 API、配置、数据模型和测试策略。
只写有代码或测试证据支持的事实，并在每个 concept 中记录 sources。
```

```text
使用 $knowledge-maintainer 审查当前分支相对 main 的改动。
只更新受影响的业务、技术和质量知识，同步相关 index.md 和 log.md。
```

记录决策、沉淀缺陷与测试知识：

```text
使用 $knowledge-maintainer 记录“订单查询引入 Redis 缓存”的架构决策。
技术细节写入 technical/adr，业务页面只保留摘要与链接。
```

```text
使用 $knowledge-maintainer，把这次重复扣款缺陷整理为质量知识。
记录触发条件、根因、修复原则、回归用例和仍需监控的风险；
把可复用场景沉淀为 Test Case，并链接需求与自动化测试。
```

渐进式查询与历史追溯：

```text
使用 $knowledge-maintainer 回答：订单服务为什么选择事件驱动架构？
请从 context-kg/index.md 开始渐进读取，只展开相关分支；
如果知识已过期或证据不足，再核对代码和配置。
```

```text
使用 $knowledge-maintainer 查询旧缓存方案，用 --history 展开归档与弃用页，
并说明替代链和适用时期，不要把历史结论当作当前答案。
```

全库治理与会话收尾：

```text
$knowledge-maintainer rebuild
```

```text
使用 $knowledge-maintainer 收敛本次会话。
先把长期结论更新到对应权威 concept，再生成简短 Session Summary，
记录决定、知识变更、验证、未决项和下次检索入口。
```

`rebuild` 的触发条件以 [Skill 触发范围](../skills/knowledge-maintainer/SKILL.md) 为准（显式调用，或前一轮已确认的知识库治理意图）；含删除、归档或移动的批次，`apply` 前会先给出清单等你确认。

## 预期目录

```text
context-kg/
├── index.md
├── log.md
├── _meta/
│   └── schema.md
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

目录可以按项目调整。`_meta/schema.md` 可选：没有它时按 Skill 的默认约定工作；OKF 的关键要求是普通 concept 有可解析的 YAML frontmatter 和非空 `type`，`index.md`、`log.md` 使用各自的保留格式，concept 间使用标准 Markdown 链接。

## 校验

在目标项目根目录运行（本地全文索引的依赖与版本以 `skills/knowledge-maintainer/scripts/context_kg_qmd.py` 中的常量与提示为准，本页只给安装命令）：

```bash
python3 "$SKILL_DIR/scripts/context_kg_lint.py" ./context-kg
```

lint 把格式错误标为 `✗`，把 OKF 允许但会降低维护质量的情况标为 `⚠`，例如断链或推荐索引缺失。退出码：`0` 通过、`1` 内容不合规、`2` 无法执行、`3` 缺少 PyYAML（未做任何判定）。

需要本地全文索引时按下表准备依赖，其余检索路径不需要：

```bash
python3 -m pip install pyyaml
npm install -g @tobilu/qmd@2.8.3
```

建议同时运行仓库自身检查：

```bash
git diff --check
git status --short --untracked-files=all
```

## 排错

### 安装后无法调用

安装命令使用本页的完整 GitHub 仓库 URL，安装后开启新的 Agent 会话。可以先列出仓库中可安装的 Skill，确认目标技能可被发现：

```bash
npx skills add https://github.com/SkyMythos-ai/skills --list
```

确认安装时选择了当前使用的 Agent；Codex 的 agent 标识是 `codex`。

### lint 提示缺少 PyYAML

校验脚本需要 Python 3 和 PyYAML：

```bash
python3 -m pip install pyyaml
```

缺依赖时脚本以退出码 `3` 结束，不再逐页误报「缺少非空 type」。看到 `3` 先装依赖，不要当成格式错误。

### 断链为什么只是警告

OKF 消费者需要容忍尚未补齐的链接，因此断链不会使 bundle 本身不合规。维护时仍应修复可确认的断链，避免渐进式导航失效。

### QMD 不可用或版本不符

命令会非零退出并保留具体错误，按需改用无状态搜索 `context_kg_search.py`，不要把它解释成知识库里没有答案。缓存是可丢弃派生物，损坏时换一个仓库外的 `--cache-dir` 重建。

### 计划被阻断或需要先确认

`check` 报告 blocker 时先修引用、快照或格式问题再 `apply`。含删除、归档或移动的批次先用 `apply --dry-run` 看 diff 与动作计数；`--expect-actions N` 可断言批次规模。

### `context-kg` 和普通 `docs/` 有什么区别

`context-kg/` 面向 Agent 和人共同消费，强调类型、来源、链接、可信度、生命周期和渐进式导航。普通 `docs/` 更适合安装指南、用户教程和发布说明。长期架构与业务知识应进入 `context-kg/`，本 Skill 的使用说明则留在 `docs/`。

## 相关资源

- [仓库首页](../README.md)
- [Skills 文档索引](README.md)
- [Skill 执行规范](../skills/knowledge-maintainer/SKILL.md)：触发范围、操作路由、按需读取
- [OKF 页面契约](../skills/knowledge-maintainer/references/okf-contract.md)：页面字段、索引与日志格式
- [生命周期对账、写入与重组](../skills/knowledge-maintainer/references/lifecycle-and-write.md)
- [全库治理](../skills/knowledge-maintainer/references/knowledge-governance.md)：分类、历史归档、rebuild 验收与恢复
- [本地全文检索](../skills/knowledge-maintainer/references/local-retrieval.md)：QMD 用法与历史内容隔离语义
- [会话结束摘要契约](../skills/knowledge-maintainer/references/session-summary.md)
- [变更记录](../CHANGELOG.md)
- [OKF v0.2 规范](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)