---
name: knowledge-maintainer
version: 1.6
description: 维护符合 Open Knowledge Format（OKF）的仓库内 context-kg 知识库。用于渐进检索、增量更新、显式 $knowledge-maintainer rebuild 治理存量知识库、分类与命名检查、有效性复核、历史归档、会话摘要、校验或从代码反向生成知识，覆盖业务、技术、质量、任务与元知识。不适用于普通文档或用户手册写作、代码实现与重构、构建/镜像/CI 语境中的 rebuild、聊天记录摘要或无长期知识沉淀的临时问答。
---

# Knowledge Maintainer

将仓库的 `context-kg/` 维护为长期、可追溯、可渐进读取的 OKF v0.2 Knowledge Bundle。仓库内 `AGENTS.md` 和 `context-kg/_meta/schema.md` 可以增加项目约束；没有 `_meta/schema.md` 时按本 Skill 的默认约定工作，不强制创建。项目约束与 OKF 冲突时说明冲突并优先产出 OKF 合规内容。

权威格式以 [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) 为准。本技能采用更严格的生产者约定：为根目录和包含多个概念或子目录的目录维护 `index.md`，以保证渐进式加载稳定可用。

## 操作路由

- **`rebuild` 短指令**：必须显式发送 `$knowledge-maintainer rebuild [bundle-path]`；只有前一轮已确认本技能的知识库治理意图时，才可以简写 `rebuild`。构建、镜像、CI 或应用重启语境中的同名命令与本技能无关，沿用其原义。执行与验收见[全库治理](references/knowledge-governance.md#rebuild-短指令)。
- **读取或回答问题**：按下节“快速渐进式检索”执行，先返回少量候选路径，再只加载回答所需的知识。
- **写入或反向生成**：先收集证据并完成生命周期对账，再按页面契约写入并同步索引与日志 → [生命周期对账、写入与重组](references/lifecycle-and-write.md)、[OKF 页面契约](references/okf-contract.md)。
- **分类、命名或生命周期治理**：→ [全库治理](references/knowledge-governance.md)。先盘点，再由当前模型结合证据填写有限批次计划；检查路径、引用和快照后应用，保留恢复记录。
- **会话收尾**：交付附简短的 KG 使用小结；需要跨会话导航时再保存 Session Summary → [会话结束摘要契约](references/session-summary.md)。
- **校验**：运行文末 lint，并按退出码区分“内容不合规”与“无法执行”。

## 快速渐进式检索

检索的完成条件是问题的各个子意图已有足够、相互一致且时效可信的证据；达到条件后立即停止，不为“可能还有更多”继续扩张上下文。

1. 提取查询中的精确键（concept 路径、文件名、Case ID、符号或接口名）、主题词、预期 `type`、适用范围和“当前/目标/历史”时间语义。先读仓库指令与根 `index.md`，按目录描述进入一个或少量相关分支。
2. 有精确键或索引路由不够明确时定位少量候选。已启用本地全文索引，或用户要求本地快速检索/文档监听时，读取[本地全文检索](references/local-retrieval.md)。其他情况使用 `context_kg_search.py`：先匹配路径与元数据，元数据零候选且有 `--scope` 时才回退该分支正文，全库正文须显式 `--body`。
3. 候选相关性按精确 ID/路径或 Case ID、标题、索引描述与 `description/tags/type`、正文命中、直接关系依次降低；可信度另按当前适用范围、`status`、`verified`、`stale_after` 和原始来源判断。关键词分高不能让 `draft`、过期或历史内容冒充当前结论，文件更新时间也不是权威性证据。
4. 只打开最高置信的少量 concept。仅当它们不能完整回答时，沿标准 Markdown 链接或 `sources[].resource` 继续一层；每扩一层重新检查停止条件。索引缺失时只列当前层直属项并读取其 frontmatter 合成临时导航，不递归预读子树正文。
5. 对易漂移事实、`draft`、已过 `stale_after`、来源不足或相互冲突的内容，转向代码、配置、测试或原始来源核验，并在回答中说明知识库状态。零候选时先扩大到全库元数据检索，最后才做限定范围的正文搜索。

历史内容的默认隔离，以及 `--status deprecated`、`--history` 的组合语义，只在[本地全文检索](references/local-retrieval.md#历史内容隔离语义)定义一次；本页与其他文档引用该节，不重复规则。

不要把 `log.md`、整个目录、全部反向链接或 Session Summary 作为普通领域查询的默认上下文。诊断检索质量时，优先报告展开的索引层数、候选数和读取正文数，而不是只报告易波动的耗时。

## 默认目录

目录分类是项目约定，不是 OKF 固定 taxonomy。仓库 schema 未另行规定时使用：

- `business/`：术语、领域模型、业务规则、功能档案、产品决策、用户洞察。
- `technical/`：架构、模块、接口契约、部署配置、代码设计规范、ADR、技术债。
- `quality/`：缺陷复盘、测试用例、测试策略、测试用例规范、自动化知识。
- `tasks/`：任务计划、进度、review、lessons 和会话摘要；不承载长期架构知识。
- `_meta/`：项目自定义 schema 等元知识。这里的普通 `.md` 仍是 OKF concept；`index.md`、`log.md` 仍遵守 OKF 保留文件规则。

长期技术知识写入 `technical/` 下对应角色：ADR 记录重要技术选择及取舍；架构说明、详细合同、持续规范、调研和运维分别归入 `architecture/`、`contracts/`、`standards/`、`research/`、`operations/`。按实际内容建立目录；项目已有有效分类时沿用，避免为形式统一迁移稳定 ID。业务页链接技术权威 concept。

测试用例、测试用例编码规范和代码设计规范是一等 concept，须各自有唯一权威入口，不能只作为其他页面或源码注释的附属段落；位置、必填字段与核对要求见[一等工程知识](references/okf-contract.md#一等工程知识)。

## 破坏性治理硬门

批次含 `delete`、`archive` 或 `move` 时，`apply` 前必须输出「路径 + 动作 + 理由 + 后继或承接目标」清单并获得用户确认；纯 `keep`/`update` 批次不要求。先运行 `apply --dry-run` 查看 diff 与动作计数，需要断言批次规模时用 `--expect-actions N`。journal 与回滚语义不变。规则与命令见[破坏性动作的人工确认硬门](references/knowledge-governance.md#破坏性动作的人工确认硬门)。

## 职责边界

- `context-kg/` 的内部结构、保留文件（`index.md`、`log.md`、`tasks/todo.md`、`tasks/lessons.md`、`_meta/schema.md`）与页面格式归本 Skill。
- 任务计划与经验的记录时机、条目的触发与验证要求，以及代码实现、质量门禁、提交/推送边界归 `personal-development`。两处只保留各自职责的一份规定，互相引用而不重复维护格式正文。

## 按需读取

| 场景 | 读取内容 |
| --- | --- |
| 页面字段、`index.md`/`log.md` 格式、链接写法、`status`/`sources`/`verified`/`stale_after` | [OKF 页面契约](references/okf-contract.md) |
| 生命周期对账、写入流程、重组与 lessons | [生命周期对账、写入与重组](references/lifecycle-and-write.md) |
| KG 使用小结、Session Summary 保存与清理 | [会话结束摘要契约](references/session-summary.md) |
| 全库分类、命名诊断、有效性判读、历史归档、rebuild 验收、恢复 | [全库治理](references/knowledge-governance.md) |
| 本地全文索引、文档监听、隔离语义与故障恢复 | [本地全文检索](references/local-retrieval.md) |

## 校验

```bash
python3 "$SKILL_DIR/scripts/context_kg_lint.py" ./context-kg
```

`SKILL_DIR` 是 Skill 的实际安装目录；Codex 全局安装时为 `~/.codex/skills/knowledge-maintainer`（此处仅作说明，可复制命令一律使用 `$SKILL_DIR`）。

退出码：`0` 通过；`1` 内容不合规；`2` 无法执行（例如 bundle 路径不存在）；`3` 缺少 PyYAML——此时未做任何 frontmatter 判定，先安装依赖再重跑，不要把它当成格式错误。

脚本检查 OKF v0.2 的 concept frontmatter、必填 `type`、可选字段结构、保留文件格式、索引链接和日志日期顺序。缺少可选索引或存在断链会报告警告，不会被误判为 OKF 不合规。随后运行与改动相关的仓库检查，例如 `git diff --check`。