---
type: Research Report
title: ADR 自动归类与生命周期治理合同研究
description: 调查 ADR 分类、有效性对账和历史归档的证据边界，并提出可检查的治理流水线。
tags: [adr, knowledge-governance, lifecycle, archive, retrieval]
status: stable
generated: { by: agent/codex, at: 2026-10-20T21:32:03+08:00 }
sources:
  - resource: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
    title: Michael Nygard 的 ADR 原文
  - resource: https://github.com/adr/madr/blob/develop/template/adr-template.md
    title: MADR 官方模板
  - resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: OKF v0.2 规范
  - resource: /technical/adr/local-fulltext-retrieval.md
    title: 本仓库的本地全文检索决策
  - resource: ../../../skills/knowledge-maintainer/scripts/context_kg_qmd.py
    title: QMD 检索状态过滤源码
  - resource: ../../../skills/knowledge-maintainer/scripts/context_kg_search.py
    title: 无状态搜索过滤源码
---

# ADR 自动归类与生命周期治理合同研究

本页保存实现前的只读调查与当时能力基线；后续全库治理实现及当前边界见[治理规范](/technical/standards/knowledge-bundle-governance.md)。

## 结论与适用边界

建议先建立 **可审阅的 ADR 治理提案**，再考虑自动应用：本地脚本收集文件、引用和变化；当前宿主模型判断决策对象、适用范围及证据冲突；确定性检查器生成并校验移动、合并、归档或删除计划；通过检查后在隔离工作区应用，最后复查当前检索与历史检索。分类可以辅助生成目录，失效处置必须以批准记录、替代关系和实际证据为依据。本文是研究和拟议合同；未修改 Fusion Harness、未迁移 ADR，也未实现治理工具。

后续讨论已扩展到整个知识包。跨 business、technical、quality、tasks 和 _meta 的分类、稳定命名及分角色生命周期规则见 [全库治理规范草案](/technical/standards/knowledge-bundle-governance.md)；该页仍为 draft，不是 Fusion 已生效规则。本文保留 ADR 专项的盘点事实和处置边界。

本仓库已有的 [knowledge-maintainer Skill](../../../skills/knowledge-maintainer/SKILL.md) 规定生命周期对账、索引与入链修复，以及 `draft`、`stable`、`deprecated` 三个 OKF 状态。其 [本地检索合同](../../../skills/knowledge-maintainer/references/local-retrieval.md) 和 [QMD 决策](/technical/adr/local-fulltext-retrieval.md) 已覆盖无模型全文召回、变更 hash 对账、默认过滤 `deprecated`、显式 `--history` 和原文 hash 核验。已通过 CodeGraph 定位并核对 [QMD `_eligible`](../../../skills/knowledge-maintainer/scripts/context_kg_qmd.py) 第 356–376 行和 [无状态搜索](../../../skills/knowledge-maintainer/scripts/context_kg_search.py) 第 242–256 行：两者默认按 `deprecated` 状态过滤，**尚不按 `archive/` 路径过滤**；`archive/old.md` 若仍标 `stable`，普通搜索仍可能命中。**新缺口**是 ADR 专属的分类建议、决策批准和实现证据判读、跨页替代关系校验、可回滚的批量移动/归档计划，以及活动导航与历史导航的双重隔离；现有检索能力不能自行宣布 ADR 失效。

## Fusion 当前目录盘点

只读快照根目录为 `/Users/chuntao.liao/Github/apigo-oversea/enterprises/fusion-harness/context-kg`，HEAD 为 `ebc967e92fce0aac8bfc7755a7cf246738ab878d`；以下包含工作区状态，不把并行未提交资料当作已交付事实。`technical/adr/index.md`、`bot-personal-projects.md` 已有修改，`projects-agent-threads-kanban.md` 未跟踪；本轮均未改动。

| 当前观察 | 数量或例子 | 能证明什么 |
| --- | --- | --- |
| `technical/adr/` 普通 Markdown concept | 78 篇、0 个子目录；另有 index/log 两个保留文件 | 决策发现全部依赖一张平铺索引。 |
| 元数据 `status` | 61 stable、11 draft、4 deprecated、2 缺 frontmatter | 这是声明状态，不是逐篇有效性或实现验收结论。 |
| 索引覆盖 | 76/78，未见重复和失效目标 | `official-business-mcp.md`、`platform-assistant-diagnostic-delegation.md` 未入索引，且缺 frontmatter。 |
| 角色混合 | 72 Architecture Decision，ADR/Design Proposal/Product Design/Technical Design 各 1，2 篇缺 type | 需要判断知识角色，再整理主题目录。 |
| 机器可读证据 | 35/78 有 `sources[].resource`；1/78 有 `verified`，该页含 5 条复核记录 | 证据字段不充分；不能因此断言其余 77 篇未做过人工或正文内验证。 |
| 持续复核入口 | 未发现 `stale_after`、主域、显式替代链等字段 | 难以稳定收敛受变更影响的页面；缺字段本身并非 OKF 不合规。 |
| 长篇材料 | 前端规范 962 行、数字员工方案 917 行、已废 Pi 方案 812 行 | “只搬目录”不能分离当前规则、详细合同和历史设计；行数不是自动删除标准。 |

上述是元数据、索引和局部正文证据，不是对 78 篇决策逐一核对代码或业务现状后的失效清单。抽读了 `pi-script-workflow-runtime.md`、`warpgate-platform-ssh-integration.md`、`sandbox-provider-v2-portability.md`、`agent-cowork-assistants-retired.md` 和前端规范的相关段落。其中 Pi 页首明确写已被新的 Workflow 基线取代，Warpgate 页首明确声明当前不提供原生 SSH；它们是归档审查线索。反例是“停用 Agent Cowork 助手，由 Fusion Bot 替代”：这篇记录退役决定本身，`stable` 不因标题含“停用”而错误。

候选主域可先用 `agent-runtime/`、`collaboration/`、`workflow/`、`sandbox/`、`knowledge-memory/`、`channels-delivery/`、`platform/`、`console/`；这是待对账的导航草案，目录实际建立取决于页面归属，不要求凑齐空分类。每个 ADR 只选一个主域，其他关注点用标签与链接表达。每域 `index.md` 应先展示少量当前决策与明确的目标决策，再提供历史入口，使用户先看“当前为什么这样做”，而不必逐篇阅读历史全文。

## 原始资料所支持的语义

- [Nygard 原文](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)把 ADR 定位为一项重要决策及其背景、后果；`proposed` 表示相关方尚未同意，`accepted` 表示已同意。原作者主张旧决策被推翻时保留并标明 `superseded`、指向新 ADR，这是历史保留的可选设计依据，并非 Fusion 的现行约束。文章还明确长期意图可以先于系统改造记录。
- [MADR 官方模板](https://github.com/adr/madr/blob/develop/template/adr-template.md)把状态及决策者作为可选元数据，示例包含 `proposed`、`rejected`、`accepted`、`deprecated` 和指向替代 ADR 的 `superseded`；其 `Confirmation` 单独询问如何确认实现或遵循决策，`More Information` 可记录团队同意及何时实现、复审。因此批准与落地不能折成一个布尔值。这些词是 MADR 模板选项，不应原封不动塞进 OKF `status`。
- [OKF v0.2 §5.4–5.5](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)仅定义 `draft`、`stable`、`deprecated`：后者为链接和历史保留、已非当前内容；`stale_after` 只表示需要重验的时间信号。§5.2 区分内容生成与验证时间，§6 容许标准 Markdown 链接，§8 容许分层索引。故过期、文件修改时间、词法检索排名，都不构成“已被替代”的证明。

## Fusion 现行规则与待决策略

已读 Fusion Harness 的 `context-kg/_meta/schema.md`、`context-kg/technical/standards/development-workflow.md` 和 `context-kg/technical/adr/index.md`。其中开发规范明确要求“ADR 写完不改，过时即删”，不保留 `deprecated/superseded` 页面；决策变化时新写一篇并删除旧篇，由 Git 历史追溯。相对地，索引仍列有标题标明已废弃、已撤回、已暂停或正文描述已替代的历史页；这说明当前目录存在需要对账的事实，但不能据索引标题推断这些页都该删或都该归档。

用户提出“失效方案删除或归档供需求历史”的方向、Nygard/MADR 的历史留存方式和 knowledge-maintainer 对有审计价值旧页的 `deprecated` 约定，与 Fusion 当前“过时即删”冲突。**归档需要同步修订 Fusion 项目策略**。本轮只列出候选、冲突、所需证据和治理方案，不把研究报告当成已执行迁移。若继续沿现行规则，历史通过 Git 版本和外部需求记录找回；若采用归档路线，应同时明确历史保存条件、默认检索隔离和来源修复规则。无论选哪一种，已批准但尚未实施的目标决策不能仅因代码尚未符合而删除；代码差异应按缺陷、技术债或待迁移调查。

## 最小知识合同

保持 OKF 的 `status` 三值，不增设并行状态机。ADR 正文保留简短的“决策角色/适用范围/批准依据/生效条件/实现证据”说明；缺批准依据则写为提议，`status: draft`，不能当作现行约束。经批准的目标 ADR 可为 `stable`，但须明确“目标、尚未实施”及生效条件；实现与验收要用独立代码、配置、迁移、测试或运行证据核对。`stable` 是可消费知识状态，**不是**“代码已实施”的同义词。规范性有效性由批准及生效条件决定，当前实际行为由代码等证据决定；新决策已批准但尚未到生效条件时，旧决策不能提前退场。发现代码与批准 ADR 不一致，应记录差异和证据，不把代码缺陷追认为新决策；批准被撤销或新 ADR 接替，须有相应决策证据。

分类以 ADR 的**主要决策对象及长期维护责任**为准，而不是文件名热词。先按现有产品域和维护边界建立有限的 taxonomy。跨域 ADR 只放一个主域，通过 tags 和标准链接指向相关域；不能复制出多份“当前决策”。分类置信不足、同一范围有多篇互斥 ADR、找不到明确拥有者时保持原位并集中复核，不能硬归类。目录改变只改善导航，不改变决策有效性。还须先辨认**知识角色**：现有目录混有设计提案、持续生效规范与长篇详设，适合迁往 `standards/` 或相应合同 concept 的，应先提取真正的决策，再决定知识归属；不能把全部文件机械移入 ADR 子目录。名称含“退役”的 ADR 也可能记录当前有效的退役决定，标题词不能作为归档触发器。只被部分替代的长篇文档，须先分离或迁出仍有效的独有内容，不能整页提前归档。

若 Fusion 批准归档，建议在 `technical/adr/archive/<主域>/` 保留**有审计、迁移、兼容或需求沿革价值**的旧 ADR 原文，标记 `status: deprecated`，页首说明适用时期、失效理由、替代页链接及判定证据；活动索引只列当前和明确标注为目标的 ADR，归档索引只从历史入口可达。对于旧结论完全被覆盖、无独有历史价值的页，先迁移仍有效的信息，再按项目规则删除。原文保留意味着不重写旧决策内容；归档说明可作为最小元数据/页首附记，是否容许这一例外也需在 Fusion 规范中明示。若严格禁止对已写 ADR 的任何改动，可由独立归档清单承载理由、时间、证据及替代链，并移动未改的原文。

## 无新模型依赖的治理流水线

1. **收集事实**：本地枚举 ADR、分层索引、`sources[].resource`、标准 Markdown 入链、路径和 Git 变更；按内容 hash 建快照，区分文件缺失、读取失败与真实删除。只把变化事件用于缩小候选，定期全量对账补漏。静态扫描可发现孤儿、断链、重复标题、过期信号和可能的跨域页，不能判定决策批准或失效。
2. **语义提案**：当前宿主模型每批最多处理 10 篇候选 ADR，先读元数据和决策段，仅在不足以判断时展开直接关系和原始批准/实施证据，输出“主域、决策对象、范围、生效时期、是否批准、实现证据、是否存在替代决策、剩余历史价值、未决点”。每个判断附文件与片段位置、证据类型、相反证据。缺证据时输出 `review`，不输出猜测性删改。可选便宜子模型仅在宿主已有能力时做初筛，由当前 Agent 复核；脚本不持有新推理凭据。
3. **确定性计划**：每项动作写明 `move | archive | merge | delete | keep | review`、旧/新路径、预期 hash、主域、适用范围、替代目标、理由、证据链接、需更新的入链/索引/来源及预期影响。检查器拒绝同范围同期间两个无说明的当前结论、替代环、无终点替代链、路径冲突、未修复的内部断链、指向删除页的来源、无证据的删除和跨任务文件。替代链终点可以是当前决策，也可以是有依据的撤回/终止；取消方案没有后继 ADR 时不伪造替代链接。合并须证明有效独有内容已迁移；移动应保留可追溯的旧路径映射。
4. **隔离应用**：在专用 worktree 或临时复制中基于预期 hash 生成完整 diff，完成格式 lint、链接检查、索引检查和新旧查询；只有全部通过才将本任务文件的精确补丁应用到目标工作树。若目标变动则停止并重新提案；任一步失败，回滚本轮应用的文件，保留用户原有 dirty/untracked。阶段性预览可供人审阅；此合同不授权自动提交、推送或改 Fusion 规范。
5. **发布检索视图**：权威仍是原文与分层 `index.md`；QMD/无状态搜索只是可重建候选索引。拟新增的普通领域查询同时排除 `archive/` 路径和 `deprecated`，防止一处标记遗漏；**现有脚本仅有状态过滤，路径隔离尚待实现**。`--history` 显式纳入归档并展示替代链、理由及原始证据，不能把历史命中直接当当前答案。QMD 同步失败时使用无状态搜索；两种路径均以实时文件及来源校验为准。

增量触发应接在“需求或决策确认、更新知识、实现影响既有决策”这些宿主工作流上：先沿来源与替代关系找直接影响项，再做有限复核。文件 watcher 只能发现文件改变，不会自行理解未写入文件的新需求，也不会证明某个旧决定已经失效。全库盘点用于首次接入或显式治理；普通会话只维护影响范围。

历史导航按“主题 → 需求/约束变化依据 → 决策 A → 决策 B → 各自生效条件与实施证据”组织，引用旧原文或可访问的 Git 固定版本。只追踪决策变化，不把每次措辞修改都当作新需求版本；ADR 提供技术决策沿革，完整需求历史仍须关联产品规格、Issue 或批准记录。最终治理摘要按域展示 keep/move/archive/merge/delete/review 的动作、依据和冲突，用户重点看少数未决判断，而不是重读全部 ADR。

## 最小验收场景

| 场景 | 必须观察到的结果 |
| --- | --- |
| 已批准且已生效的新 ADR 接替旧 ADR，旧页有需求历史价值 | 旧原文可从 `--history` 找到；普通查询只给新规范性结论；替代链到达唯一当前页；所有入链、来源和索引可解析。 |
| 新 ADR 仅是 proposal，旧 ADR 仍有效 | 旧页继续作为当前结论；提案保留 draft/目标身份；不得预先归档旧页。 |
| 批准目标与当前代码不同 | 报告“目标未落地/疑似偏离”并列证据；不能把代码状态改写成获批决策，也不能把目标认作已实施。 |
| `stale_after` 到期或只更新 mtime | 进入复核队列；无新批准或实施证据时不自动归档/删除。 |
| 一页跨两域、重复方案、替代环或断链 | 保持单一主域或输出 review；循环/断链使计划失败，目标工作树无部分改动。 |
| 原页无历史价值且已被完整取代 | 有批准及迁移证据后才可删除；旧链接全部处理；Git 历史仍可追溯。 |
| 历史页误标 `stable` 或活动页误放 `archive/` | 路径与状态双重隔离发现不一致并报错，普通查询不泄露历史结论。 |

## 自动化边界与策略选择

自动化可完成枚举、hash 对账、链接图、候选分类、计划校验和隔离试运行；**不得仅凭相似度、过期时间、文件时间、代码差异、索引标题或模型自信度自动批准、废弃、删除 ADR**。涉及仍有消费者、兼容迁移或无法定位批准记录的页面，保留 `review` 并呈现冲突证据。

建议后续治理计划同时给出“有价值者归档、无价值者删除”的项目规范修订、归档附记方式、主题目录映射和首批 dry-run diff。低确定性结论集中放入 review，其余按选定 taxonomy 执行；先在一小组 ADR 核对新旧查询与需求时间线，再扩到全库。本研究没有实施这些改动。
