---
type: Knowledge Governance Standard
title: Context-KG 分类、命名与有效性治理规范
description: 规定全库的目录角色、稳定命名、有效性证据和历史隔离，记录本地治理工具及其验证边界。
tags: [context-kg, naming, taxonomy, lifecycle, governance]
status: stable
sources:
  - resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: OKF v0.2 规范
  - resource: /technical/research/adr-governance-2026-10-20.md
    title: Fusion ADR 只读盘点与生命周期研究
  - resource: ../../../skills/knowledge-maintainer/SKILL.md
    title: knowledge-maintainer 当前生产者与生命周期约定
  - resource: ../../../skills/knowledge-maintainer/references/knowledge-governance.md
    title: 随技能携带的全库治理执行规则
  - resource: ../../../skills/knowledge-maintainer/scripts/context_kg_govern.py
    title: 本地盘点、计划检查、应用与恢复工具
---

# Context-KG 分类、命名与有效性治理规范

## 状态与适用范围

本页记录 knowledge-maintainer 采用的全库治理约定，覆盖 `business/`、`technical/`、`quality/`、`tasks/`、`_meta/`、自定义分支及附件。可随技能安装的执行入口为[全库治理流程](../../../skills/knowledge-maintainer/references/knowledge-governance.md)，命令以脚本 `--help` 为准。下文区分 OKF 格式约束、生产者默认和项目特例；命名偏好不作为 OKF 合规门禁。实现只修改本技能仓库，未修改 Fusion Schema 或迁移其页面。

用于新增页面、实质更新和显式治理；仅因老文件名与新风格不同不触发全库改名。实际项目可调整分类和文件名语言，并在本地 schema 记录差异。普通会话只对账变更影响范围，首次盘点或明确治理才扫描全库。

## 全库盘点依据

2026-10-20 只读扫描 Fusion Harness 当前工作区：164 个 Markdown，包含 19 个 `index.md`/`log.md` 和 145 个普通 concept；其中 143 篇有 type，2 篇缺 frontmatter。另有 2 个 TSV 附件。分支 concept 数为 business 5、technical 116、quality 9、tasks 14、_meta 1。`type: Concept` 的 4 篇仍是普通 concept，不是保留文件。

所有现有 Markdown 文件名均符合小写 kebab-case，未发现超过 60 字符的文件名；因此当前重点是**语义、文档职责、日期表达和路径组织**，不是大小写整改。长度扫描只是线索，不是固定上限门禁。`quality/everos-memory-runtime.md` 与 `technical/operations/everos-memory-runtime.md` 等跨目录同名是合法的不同 concept ID，不能当作重复文档删除。

当前 166 个文件中，147 个被跟踪，18 个因 `tasks/` 规则被忽略，另 1 个 ADR 未跟踪且未忽略。这些是工作区盘点数据，不等同于 GitHub 已发布知识；分类、命名或归档不能自动改变其跟踪和共享边界。未将忽略文件正文复制到本仓库。

## 目录、文件名与标题的职责

| 载体 | 承担的职责 | 例子 |
| --- | --- | --- |
| 目录 | 知识角色、主主题与导航边界 | `technical/contracts/memory/` |
| 文件名 | 稳定、可辨认的语义标识 | `file-memory-runtime.md` |
| `title` | 面向读者解释对象、职责和适用范围 | 个人与项目文件记忆运行合同 |
| frontmatter 与正文证据 | 类型、状态、来源、适用时期及验证边界 | `type`、`status`、`sources`、`verified`、`stale_after` |

按 OKF，相对路径去掉 `.md` 是 concept ID。标题可以随表达改善而更新，路径应尽量稳定；文件改名和目录移动都要按 ID 迁移处理，不是单纯排版。不同目录可有同 basename，同一页面只有一个主要归属，其余主题通过 tags 和标准链接表达。

## 分类规则

先识别知识角色，再在确有多个独立主题时按领域下钻。以下是候选路由，不要求创建全部子目录，也不要求现有少量平铺文件立刻迁移：

| 根分类 | 主要知识角色与可选子目录 | 维护重点 |
| --- | --- | --- |
| `business/` | `domain/` 术语与模型、`requirements/` 产品需求、`rules/` 业务规则、`decisions/` 产品取舍 | 批准依据、适用对象、生效条件和需求变更原因。技术决策仍路由到 technical/adr。 |
| `technical/` | `architecture/` 总览、`adr/` 技术决策、`contracts/` 接口与运行合同、`standards/` 持续规范、`research/` 调研、`operations/` 运维 | 区分决策理由、规范性目标、实际实现、操作步骤和研究证据。 |
| `quality/` | `test-cases/` 测试用例、`standards/` 测试表达与质量约束、`verification/` 验证记录、`incidents/` 缺陷复盘 | 区分要验证什么、如何表达测试、已经执行过什么及其结果。 |
| `tasks/` | 计划、Review、任务记录、`session-summaries/YYYY/MM/` 连续性导航 | 只承载过程与恢复入口；稳定结论迁到其权威角色，保留链接。 |
| `_meta/` | schema、taxonomy、全库治理约定 | 描述知识包自身，不混入产品架构或业务需求。 |

ADR 记录一次重要选择的背景、决定和后果；详细合同、持续规范和产品需求即使与该决定有关，也有各自的权威页面，不全部塞进 ADR。一个页面只有部分内容过时时，先迁出仍有效的独有内容再处置旧页。类型同义写法可由项目 schema 选择推荐名，但读取器仍接受未知 type；目录与 type 不相等只能作为复核线索。

## 文件名与标题

1. **稳定语义。** 新文件默认英文小写 kebab-case，名称表达稳定对象，必要时补职责或关注点，例如 `delivery-authorization.md`。单对象名、常用缩写和协议名也可使用，不强制所有名称都符合二段式模板。中文或其他项目既有命名规范作为本地特例处理。
2. **消除无助于区分的重复。** 已有 `adr/`、`contracts/`、`standards/` 等目录语境时，不机械再加 `-adr`、`-contract`、`-standard`。只有能减少歧义时才补角色词；短名称优先于把所有主题连接成一个长文件名。
3. **状态放在状态中。** 新的长期权威页默认不用 `final/latest/current/draft/deprecated` 或“最终版/最新版”表达文件状态。用 `status`、证据及明确的适用范围表达；标题也应说明具体对象和职责，避免“最终完整技术方案”这类无法验证的承诺。现有此类名称先复核，不按词匹配自动改名。
4. **版本与日期有语义才保留。** 普通长期权威页不以文档修订次数追加 `v2/v3` 或日期；真实协议、产品或领域版本确有兼容差异时可以保留版本名。研究快照、验证报告、事件记录、任务记录和 Session Summary 可用 `YYYY-MM-DD-<topic>.md` 或 `<topic>-YYYY-MM-DD.md`，沿用本分支惯例，不为日期前后位置改名；日期取实际事件或记录基准，不从 mtime 推断。持续研究结论也可用稳定主题名，将时间放在正文中。
5. **保留领域标识。** Test Case、需求和缺陷的独立标识继续使用既有 ID 约定，例如正文或项目扩展字段的 `TC-ORDER-042`；新增文件可取 `tc-order-042.md`。不为改大小写而重写既有稳定路径，不把业务 ID 当成 OKF concept ID 的替代实现。
6. **保留入口。** 任意层级的 `index.md`、`log.md` 是 OKF 保留文件。`tasks/todo.md`、`tasks/lessons.md`、`_meta/schema.md` 等虽是普通 concept，却已有工具或项目约定，默认保留其路径；迁移须单独处理调用方。
7. **标题服务阅读。** 推荐使用中文准确说明对象和职责；同名在上下文中难以区分时补适用范围。标题不需要是文件名的逐字翻译，标题变化也不要求路径跟着变化。用户可通过目录、title/description/type/tags 理解文档，不靠记忆长文件名。

例如，下面展示的是具体治理计划可采用的职责表达，不是已执行或必须执行的迁移：

| 现有页面 | 可考虑的目标表达 | 前提 |
| --- | --- | --- |
| `business/observability-page-design-requirements.md` | `business/requirements/observability-page.md`，标题“可观测性页面需求与验收边界” | 需求仍有效，且该角色确有分类收益；保留批准与生效线。 |
| `technical/memory-runtime-contract.md` | `technical/contracts/file-memory-runtime.md`，标题“个人与项目文件记忆运行合同” | 核对生产者、消费者和引用；并非因为旧名违反 kebab-case。 |
| `quality/lark-group-materials-verification.md` | `quality/verification/lark-group-materials-<run-date>.md` | 确认它记录一次运行，日期来自运行证据；若是持续维护的验收合同则采用稳定主题名。 |
| `quality/everos-memory-runtime.md` 与 `technical/operations/everos-memory-runtime.md` | basename 可以保持相同 | 前者是验证证据，后者是运维步骤，角色和来源不同，不是重复副本。 |

## 元数据与有效性

沿用现有 OKF 字段：`type` 始终必填；生产者维护简明的 `title/description/tags/status`；来源用 `sources[].resource`；验证用 `verified`；需要复核的时间信号用 `stale_after`。这些推荐字段的缺失不全部构成 OKF 格式错误。项目已有 `updated` 和其他扩展字段读写往返时保留，不再新增一组同义状态字段。

`status` 保持 `draft/stable/deprecated`。`stable` 不等于需求已经生效、代码已经实现、部署或业务验收已经通过；`verified` 也只证明记录所声明的验证范围。来源、批准、生效条件和实际实现的差异先在正文及链接中写清，扩展字段仅在确有机器消费需要时由 schema 定义。

| 知识角色 | 如何复核有效性 | 历史处理 |
| --- | --- | --- |
| 需求、业务规则、领域模型 | 对照批准依据、适用对象、生效条件与当前产品要求；区分目标和实际偏离 | 重大变化链接前后需求及理由；新目标未生效时不能提前撤掉旧规则。 |
| ADR、架构、接口与运行合同 | 对照决策证据、后继关系和生产/消费兼容性；代码不一致也可能是未实施或缺陷 | 保留重要取舍及兼容沿革；部分替代先处理仍有效内容。 |
| 设计/代码/测试规范 | 核对适用范围、已批准例外与受约束实现；偏离不自动成为新规范 | 已失效约束退出当前入口，必要时保留原适用时期和替代规范。 |
| 研究与验证报告 | 明确时间点、版本、对象、环境和证据层级；旧快照仍可准确记录过去 | 新证据影响当前采用结论时更新当前入口；历史结果不改写成当前能力。 |
| Test Case、缺陷复盘 | 核对需求、边界与回归价值，case 和自动化映射分别对账 | 未自动化不等于无效；自动化映射或代码变化不等于执行通过。 |
| 任务 Review 与 Session Summary | 长期事实是否已有权威页、是否仍用于接续 | 无独立价值者清理；需要追溯时保留时间点与权威链接，不成为另一份长期规范。 |
| schema 与治理约定 | 核对当前消费者、保留路径与兼容策略 | Schema 演进需验证全部受影响角色，不能只核对 technical。 |

## 归档与需求沿革

判定结果使用 `keep/move/merge/archive/delete/review` 等计划动作，不把它们混成 OKF status。`stale_after` 到期、文件名含“停用”、mtime 较旧、没有反向链接或模型相似度，只能作为线索，不能单独证明失效。没有反向链接的根知识、外部来源或新 concept 仍可能有价值。

有需求、决策、迁移、审计或回归价值的失效内容保留历史；重复且无独有价值者在有效信息迁出后合并/删除。历史可由带有理由与后继关系的归档页，或确实可访问的固定 Git/Issue 版本承载；不能只给一个不可访问的旧路径。被 Git 忽略的任务页不能仅靠当前仓库 Git 历史恢复，更不能在整理时自动转为共享文件。

候选归档位置为 `<分支>/archive/<主题>/`，主域和历史量足够大时也可在角色目录内设 archive；一个 bundle 选定惯例后由 schema 声明。历史页标记 `deprecated`，记录适用时期、失效依据和后继链接；无后继的撤回或终止记录具体理由，不伪造替代链。活动索引只概括当前及明确的目标知识，历史从专门入口发现。需求沿革按“变更依据 → 原规则/决定 → 新规则/决定 → 生效与实现证据”导航，不能以 ADR 代替全部产品需求历史。

普通检索同时按归档路径和状态隔离历史：两种搜索默认排除任意层级的 archive 目录，即使其页面误标 stable；`--history` 才展开归档与摘要。显式 `--status deprecated` 保留非归档弃用页的查询入口。Fusion 调查时的 ADR 规则规定“过时即删”；在该项目采用归档前须先解决本地规则与目标策略的冲突，本技能实现没有改写其政策。

## 可检查迁移与增量维护

1. 本地扫描路径、元数据、索引和直接关系；当前宿主模型按需判读对象、知识角色和证据，生成有限批次建议。例行维护只处理受影响项，不为形式统一重新读取全库正文，也不需要额外的推理模型或凭据。
2. 计划逐项记录旧/新 concept ID、源 hash、动作、理由、证据、目标冲突及全部引用修改。仅语义歧义或分类确有收益时迁移路径，其余可先改善标题、描述和分组导航。大小写不敏感文件系统上的名称碰撞也需检查。
3. 修复标准 Markdown 根/相对链接、`sources[].resource` 中的真实路径，以及项目扩展 `links` 和其他已知路径型字段；相对链接必须按迁移前后位置分别解析。URL 和非文件的来源描述保持其原有语义，不能盲目字符串替换。还须核对代码、配置、AGENTS、Skill 和外部消费者；无法定位的消费者集中复核。
4. 同步受影响 concept、父索引、必要祖先入口及适用日志，记录路径映射。保留文件格式和未知元数据；附件按所有者引用维护，TSV/图片/JSON 不因不是 Markdown 就删除或强加 frontmatter。缓存仍在 bundle/Git 外，文件是否被跟踪由项目规则和既有授权决定。
5. 在内存拟议树生成 diff；核对全库文件集合与源 hash 未被并行任务改变，再做限定应用。仓库外保存私有 journal 与备份，逐文件原子写入；失败尝试恢复，恢复冲突时保留证据并停止，不覆盖并行修改。保留原 dirty/untracked，不隐含提交、推送或部署。
6. 检查格式、分类/命名诊断、链接、索引、替代链与新旧查询，启用全文索引时执行 sync。项目可要求本次迁移不新增内部断链，但 OKF 消费者仍需容忍未解析引用；不能把所有旧断链误报为新增违规。语义归档、替代环和外部消费者判断仍需证据，不由正则检查代替。

## 验收与当前边界

验收覆盖：全部分支都参与盘点；同 basename 不误判重复；新命名缺省与既有 ID 例外可区分；日期快照与持续权威页可区分；真实领域版本不被抹除；批准目标和实际实现不混同；忽略文件及未知元数据不丢失；改名后相对链接和来源仍可定位；归档默认隐藏且历史可读；失败可恢复，遇到并行改动保留诊断与备份。

实现入口为 `context_kg_govern.py audit/plan/check/apply/recover`：盘点与命名诊断不读取整库正文进入模型，分类建议不自动成为迁移动作；宿主依据有限候选和证据填写计划，脚本检查 hash、路径、引用、索引及替代环，并提供 diff 和恢复记录。工具验证证据文件及 hash，不能代替模型判断批准、生效、部分替代、历史价值或未知消费者。

外部静态路径命中会阻断，动态构造路径、未识别的项目扩展和外部仓库消费者由宿主补查。移动文档的内部引用、真实来源路径和已知扩展关系由工具修复；静态扫描无命中不证明没有消费者。多文件应用不提供跨文件原子快照。分类、命名和失效处置不调用额外模型，也没有自动重命名任何 Fusion 页面。

2026-10-20 实现验收：77 项测试全部通过，包含真实 QMD 2.8.3 集成；隔离 fixture 覆盖跨目录引用重算、组合处置、归档与恢复、快照冲突、失败恢复及文件权限。技能格式与本仓库知识库 lint 通过。此证据证明已覆盖的工具行为，不证明 Fusion 全库语义有效性或其项目归档政策已变更；详细结果见[任务 Review](/tasks/todo.md)。
