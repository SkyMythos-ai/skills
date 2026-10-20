# 全库分类、命名、有效性与历史归档

在分类整理、命名检查、全库审计、需求沿革或失效清理时读取。普通写入只治理受影响的 concept；明确要求全库审计时才扩大扫描。脚本使用 Python 3 与已有的 PyYAML，不调用模型。语义分类和有效性判断复用当前宿主模型，按候选分批展开正文与证据。

## rebuild 短指令

用户发送 `$knowledge-maintainer rebuild`，即要求对当前项目 `context-kg/` 执行一次完整的存量治理。可在后面指定另一个 bundle 路径，如 `$knowledge-maintainer rebuild /project/context-kg`。目标只在范围无法从项目与会话确定时澄清。已明确处于本技能的知识库治理语境时，单独 `rebuild` 等价；编译、镜像或其他应用的 rebuild 沿用其原义。

这是由当前 Agent 执行的 Skill 指令。底层使用已有 `audit/plan/check/apply/recover`；全文索引的 `sync` 继续负责检索同步。

执行至以下条件满足：

1. 读取项目规则、schema、索引及工作区状态，盘点整个 bundle，覆盖全部知识分支、忽略文件和附件。
2. 当前模型根据分类、命名、到期与引用线索分批读取必要正文和原始证据，为各项记录保留、更新、迁移、合并、归档、删除或待复核的处置依据。稳定 ID 优先保持；证据不足的项目保留待复核，不按名称或时间猜测失效。
3. 由 Agent 填写有限批次计划，检查实际 diff 和快照；在本次治理授权范围内应用证据明确且检查通过的批次，并修复内部引用、相关索引和日志。遇到策略冲突、外部消费者或并行改动时记录阻断，继续独立批次；单纯生成空计划不算完成。
4. 将批次进度、完成项、待复核与阻断项记录到项目已有任务页或 Review，执行 lint 与当前/历史查询验证；已启用 QMD 时执行 sync。最终按实际覆盖范围报告结果、恢复记录及未解决项。

指令范围为知识库整理，沿用已有提交、推送和部署边界。首次启用 Skill 不自行运行 rebuild；日常变更继续按增量维护处理。

## 分类与稳定 ID

先读项目 `AGENTS.md`、`_meta/schema.md` 和已有索引，确定适用分类、历史策略与共享边界。以下是没有项目约定时的生产者默认；未知类型、自定义根目录、中文文件名和既有稳定路径均可保留。项目规定“过时删除”时，先结合本次授权解决策略冲突，再执行归档；工具不替项目决定政策。

| 分支 | 知识角色与建议位置 |
| --- | --- |
| `business/` | `domain/` 术语与模型、`requirements/` 需求、`rules/` 规则、`decisions/` 产品取舍 |
| `technical/` | `architecture/` 架构、`adr/` 决策、`contracts/` 合同、`standards/` 持续规范、`research/` 调研、`operations/` 运维 |
| `quality/` | `test-cases/` 用例、`standards/` 质量规范、`verification/` 执行证据、`incidents/` 复盘 |
| `tasks/` | 计划、Review、lessons、`session-summaries/YYYY/MM/` 连续性导航 |
| `_meta/` | schema、taxonomy、知识包治理约定 |

按知识角色分类，再在确有多个独立主题时按领域下钻。主归属只有一个，其余通过 tags 和标准链接关联；目录数量以导航收益为准，按实际内容建立。ADR 表达背景、选择和后果，详细需求、合同和持续规范各有权威页面。任务中的长期事实迁到相应角色，任务页保留过程与链接。

文件名承担稳定标识，`title` 服务阅读。Concept ID 是 bundle 相对路径去掉 `.md`；改名、移动都属于 ID 迁移，标题改善不要求改路径。

- 新页面默认英文小写 kebab-case，以稳定对象和必要职责命名，如 `delivery-authorization.md`；不强制二段式名称，不机械重复目录中的 `adr/contract/standard`。
- `final/latest/current/draft` 等修订状态词产生复核提示；状态用 frontmatter 和生效说明表达。词命中本身不触发改名或失效处置。
- 真实协议/领域版本可保留 `v1/v2`；长期权威页的文档修订次数不作为文件名版本。
- 研究快照、执行记录、事件、任务和 Session Summary 可用日期前缀或后缀，沿用分支惯例；日期来自事件证据。持续研究也可采用稳定主题名。
- 中文标题准确说明对象、职责与范围，无须逐字翻译文件名。不同目录相同 basename 是合法的不同 ID。
- `index.md`、`log.md` 是保留文件；`tasks/todo.md`、`tasks/lessons.md`、`_meta/schema.md` 是有工具消费者的普通 concept，默认保持路径。
- 附件随所有者引用维护，保留二进制与原格式。未知 frontmatter 字段往返保留；格式化可能变化，字段语义不丢失。

命名与分类诊断是生产者建议，不能冒充 OKF 格式错误。读取器继续容忍未知 type；已有路径与风格不同也不触发全库改名。

## 有效性判读

沿用 Skill 的“生命周期对账”。`status` 只有 `draft/stable/deprecated`；`stable` 不证明批准、生效、实现、部署或验收。`verified` 只证明其明确记录的范围。`stale_after` 到期只生成复核项；mtime、无入链、名称、相似度都不能单独证明内容无效。

| 角色 | 当前模型必须核对的证据 |
| --- | --- |
| 需求、业务规则、模型 | 批准依据、对象、适用时期、生效条件、当前产品要求与变更原因 |
| ADR、架构、合同 | 决策与后继关系、适用范围、生产消费兼容性；区分目标与实现偏离 |
| 代码/测试/设计规范 | 批准约束、有效例外与受约束实现；偏离记录为缺陷或待迁移项 |
| 调研、验证、事件 | 时间点、版本、环境、对象、原始证据与验证层级 |
| Test Case、复盘 | 需求与回归价值；自动化映射和已执行证据分别核对 |
| 任务与摘要 | 长期事实承接位置、接续与审计价值、忽略文件的实际可恢复性 |
| Schema 与治理约定 | 当前消费者、保留路径与兼容策略，覆盖全部分支 |

每批只展开足以判读的候选及直接证据，形成 `keep/review/move/update/archive/delete` 结论。`keep/review` 留在审计或任务 Review，不制造无意义文件改动。合并用“更新目标 + 删除来源”组合表达，先确认仍有效的独有内容已经迁入；部分失效先保全有效部分。新目标尚未生效时，旧规则仍可作为当前事实存在。无法裁决时保留明确的开放问题，不猜测归档。

## 历史与需求沿革

有取舍、审计、迁移、兼容或回归价值的旧知识归档。默认在原角色目录下使用 `archive/`，也可采用 schema 明确的分支历史目录。历史页标为 `deprecated`，保留正文，注明原路径、适用时期、失效理由、依据与后继。无后继的撤回或终止记录理由即可，不能虚构替代链。

活动索引通过历史目录发现归档，历史正文仍可被引用；需求沿革沿“变更依据 → 原规则/决定 → 新规则/决定 → 生效与实现证据”追溯。无剩余价值的重复页可删除，先核对消费者与内容承接。被忽略的文件不能只依赖 Git 历史恢复，整理也不改变它的共享边界。

两种检索默认按状态和路径隔离历史：任意目录分量为 `archive` 的页面即使仍为 `stable` 也不作为当前候选；`--history` 显式展开。`--status deprecated` 可查询非归档弃用页；归档与 Session Summary 仍需 `--history`。`archive-storage.md` 等普通文件名不属于归档路径。

## 可检查的本地治理

以下命令中的 `SKILL_DIR` 指实际安装目录。计划与审计输出放在 bundle 外；恢复状态放在 Git 仓库外。先核对工作区，不自动暂存、提交、推送或修改安装副本。

```bash
python3 "$SKILL_DIR/scripts/context_kg_govern.py" audit ./context-kg --limit 20 --output /tmp/kg-audit.json
python3 "$SKILL_DIR/scripts/context_kg_govern.py" plan ./context-kg --output /tmp/kg-plan.json
```

`audit` 盘点全部分支、保留文件、普通 concept 和附件，记录 hash、Git 跟踪/忽略边界、分类建议、命名诊断、过期及引用线索；不输出整库正文。`--limit` 约束终端显示，完整 JSON 保存在指定文件。`plan` 保存文件集合与 hash，actions 初始为空，不会按启发式自动执行重命名或归档。

由当前模型依据实际证据填写 actions。基本结构如下；完整字段以命令校验结果为准：

```json
{
  "version": 1,
  "root": "/absolute/project/context-kg",
  "created_at": "2026-10-20T10:00:00+08:00",
  "snapshot": {
    "technical/cache.md": {"sha256": "sha256-from-plan", "git_status": "tracked"}
  },
  "actions": [
    {
      "op": "archive",
      "path": "technical/cache.md",
      "target": "technical/archive/cache.md",
      "reason": "旧缓存方案已退出，保留原取舍用于迁移追溯",
      "effective_period": "2025-01 至迁移完成日，具体生效依据见记录",
      "replacement": "technical/contracts/cache-runtime.md",
      "evidence": [
        {"path": "../src/cache/config.yaml", "sha256": "actual-file-sha256", "note": "迁移完成后采用的新配置"}
      ]
    }
  ]
}
```

上例只展示字段，实际 `snapshot` 必须使用工具生成的完整快照，证据 hash 必须读取实际文件计算。治理记录时间来自计划的 `created_at`，保证相同输入的预览和应用结果一致；它不作为业务生效证据。证据路径相对 bundle，允许引用同项目中的 `../src/...`；证据说明指出其证明什么。检查器只能确认文件及 hash，证据是否足以证明生效、失效或无剩余价值由当前模型负责。

| 动作 | 计划要求 |
| --- | --- |
| `move` | `path/target/reason`；适用于明确的职责迁移，路径变化按 ID 迁移处理 |
| `update` | `reason/evidence`，`metadata` 合并字段，可选 `body` 只替换正文；保留未知元数据 |
| `archive` | `reason/evidence/effective_period`；可给 `target/replacement`，写入历史状态及可追溯说明 |
| `restore` | `target/reason/evidence`，恢复状态为 `draft` 或 `stable`；核对当前适用性后恢复活动导航 |
| `delete` | `reason/evidence/preservation`，说明独有内容承接目标或无剩余价值的依据；仍有消费者时先处理引用 |

检查并审阅实际 diff，再在任务授权范围内应用：

```bash
python3 "$SKILL_DIR/scripts/context_kg_govern.py" check ./context-kg --plan /tmp/kg-plan.json
python3 "$SKILL_DIR/scripts/context_kg_govern.py" apply ./context-kg --plan /tmp/kg-plan.json
python3 "$SKILL_DIR/scripts/context_kg_lint.py" ./context-kg
```

检查覆盖源快照、大小写碰撞、目标与路径边界、证据 hash、内部 Markdown/来源与可识别 ID 引用、索引及替代链。已有格式或断链诊断采用基线对比，拟议改动不能新增问题；这不把既有全库警告宣称为零。外部代码、配置、AGENTS 等仍引用旧路径时会阻断；先做必要的有界调用方修改，再重新生成快照计划。动态构造路径、非标准链接语法和外部仓库消费者由当前模型额外核对，不能把静态扫描无命中当作没有消费者的证明。

工具按实际路径映射修复可解析引用，移动文档自身的相对链接也按原位置解析后重新定位；URL、非路径来源描述保持原义。受影响索引保留人工导航，局部日志追加处置记录。不要用全库字符串替换或重建所有索引代替迁移。

应用使用仓库外私有 journal 与备份，逐文件原子替换；多文件过程对外部读取者不提供统一原子快照。快照过期或文件并行变化时停止，重新审阅，不强行覆盖。出现中断后使用同一状态目录恢复：

```bash
python3 "$SKILL_DIR/scripts/context_kg_govern.py" recover ./context-kg
```

恢复只撤销最近事务，接管本事务写入且未被后续改动的文件；发生冲突时保留备份和诊断，先核对双方内容。后续事务会将旧 journal 留存在私有历史目录。完成后重新检索新旧路径，确认默认查询只返回当前知识，历史查询可读归档。已启用 QMD 时按[本地全文检索](local-retrieval.md)执行 `sync`，并报告结果；查询前的对账仍会发现文件变化。
