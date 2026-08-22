---
name: knowledge-maintainer
description: 维护符合 Open Knowledge Format（OKF）的仓库内 context-kg 知识库。用于创建、更新、重组、查询、校验或从代码反向生成 context-kg，以及处理知识库、Wiki、ADR、PDR、缺陷复盘和长期项目文档。
---

# Knowledge Maintainer

将仓库的 `context-kg/` 维护为长期、可追溯、可渐进读取的 OKF v0.2 Knowledge Bundle。仓库内 `AGENTS.md` 和 `context-kg/_meta/schema.md` 可以增加项目约束；当其与 OKF 冲突时，说明冲突并优先产出 OKF 合规内容。

权威格式以 [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) 为准。本技能采用更严格的生产者约定：为根目录和包含多个概念或子目录的目录维护 `index.md`，以保证渐进式加载稳定可用。

## 操作路由

- **读取或回答问题**：执行“渐进式读取”，只加载回答所需的知识。
- **写入或反向生成**：先收集证据，再按 OKF 页面契约写入并同步索引与日志。
- **重组**：先确定目标分类，再移动页面、修复标准 Markdown 链接并重建相关索引。
- **校验**：运行随附 lint；OKF 允许但本项目不推荐的情况应报告为警告，而不是误判为格式错误。

## 默认目录

目录分类是项目约定，不是 OKF 固定 taxonomy。仓库 schema 未另行规定时使用：

- `business/`：术语、领域模型、业务规则、功能档案、产品决策、用户洞察。
- `technical/`：架构、模块、接口契约、部署配置、技术约定、ADR、技术债。
- `quality/`：缺陷复盘、测试用例、测试策略、自动化知识。
- `tasks/`：任务计划、进度、review 和 lessons；不承载长期架构知识。
- `_meta/`：项目自定义 schema 等元知识。这里的普通 `.md` 仍是 OKF concept；`index.md`、`log.md` 仍遵守 OKF 保留文件规则。

长期技术方案和架构决策默认进入 `technical/adr/`，不要落到 `docs/design/`。业务页只保留技术摘要，并链接到对应技术 concept。

## 渐进式读取

读取知识库时按层展开，完成条件是已有足够、相互一致的证据回答问题：

1. 先读仓库指令和 `context-kg/index.md`。任意层级缺少索引时，只列出该层直属文件和目录，并只读直属 concept 的 frontmatter 来临时合成该层导航；不要递归预扫子树正文或 frontmatter。
2. 根据索引中的标题、单句描述和目录入口，选择与问题相关的一个或少量分支；进入分支后重复“先读该层 `index.md`，缺失则合成当前层导航”。
3. 只打开命中的 concept。优先利用 `type`、`description`、`tags`、`status`、`stale_after`、`verified` 判断相关性、时效性和可信度。
4. 仅当当前 concept 不能完整回答时，沿正文中的标准 Markdown 链接或 `sources[].resource` 继续一层；每层重新判断是否已足够。
5. 对易漂移事实、`draft`、已过 `stale_after`、来源不足或相互冲突的内容，转向代码、配置、测试或原始来源核验，并在回答中说明知识库状态。

不要把 `log.md`、整个目录或所有反向链接作为默认上下文。用户要求全库审计、重组或批量一致性检查时，才扩大读取范围。

## OKF 页面契约

除任意层级的保留文件 `index.md` 和 `log.md` 外，每个 `.md` 都是 concept，必须是 UTF-8 Markdown，并以可解析的 YAML frontmatter 开头。`type` 是唯一始终必填字段：

```yaml
---
type: Architecture Decision
title: 缓存层选型
description: 说明缓存边界、失效策略与选型结果。
tags: [architecture, cache]
status: stable
generated: { by: human:team, at: 2026-08-22T10:00:00+08:00 }
sources:
  - id: cache-config
    resource: /references/cache-config.yaml
    title: 缓存配置
---
```

约束：

- `type` 使用简短、自解释的类型；消费者必须容忍未知类型。
- 推荐填写 `title`、单句 `description` 和 `tags`。文件名用小写连字符；concept ID 是去掉 `.md` 的 bundle 相对路径，因此不同目录可以有同名文件。
- `sources` 如出现，必须是来源对象列表；每项必须有 `resource`。不要用数字计数代替来源列表；无来源时省略该字段。
- `generated.at`、`verified[].at`、`stale_after` 使用带 UTC offset 的 ISO 8601 datetime。`generated` 如出现必须包含 `by`；`verified` 的每项包含 `by` 和 `at`。
- `status` 只使用 `draft`、`stable`、`deprecated`；缺失等同 `stable`。
- `type: Attested Computation` 时，`runtime` 条件必填；`parameters`、`computation`、`executor` 和 `attester` 按 OKF §10 的 contract 表达。
- 可以保留项目自定义 frontmatter 字段；读写往返时保留未知字段。
- 正文没有强制章节。用结构化 Markdown 表达事实，不复制大段源码。

## 链接、索引与日志

Concept 间关系使用标准 Markdown 链接：优先使用 bundle-root 相对链接，如 `[缓存层](/technical/cache-layer.md)`；也可使用普通相对路径。WikiLink 和自定义 `links` 字段可以作为仓库扩展保留，但不能替代 OKF 标准链接。

`index.md` 用于渐进式发现：

```markdown
# Technical

* [缓存层](cache-layer.md) - 缓存边界、失效策略与运维约束。
* [架构决策](adr/) - 已确认的长期技术决策。
```

- 任意目录均可有 `index.md`；索引列出直属 concept 和子目录，并带单句描述。
- 非根 `index.md` 不含 frontmatter。根 `index.md` 仅可用 frontmatter 声明 `okf_version: "0.2"`。
- 新增、删除、移动、重命名或实质调整描述时，更新受影响层级的索引。

`log.md` 是可选的目录变更记录。本技能的生产者约定是不写 frontmatter；以 `## YYYY-MM-DD` 分组，最新日期在前。维护既有条目，不改写历史。

## 写入流程

1. 定位仓库根目录，读取 `AGENTS.md`；写入时再读取 `_meta/schema.md`、目标分支索引和相关 concept。若任务规则要求，在 `tasks/todo.md` 记录计划。
2. 明确证据：代码、测试、配置、迁移、规范、讨论结论或外部来源。代码反向生成时先从入口、公开 API、模块边界、配置、schema 和测试建立能力图。
3. 按业务、技术、质量或任务过程分类。优先更新已有 concept，避免近义重复；设计决策写入 ADR。
4. 写持久知识而非任务流水账。区分代码证明的行为、测试覆盖的行为和未经证实的产品意图；不确定内容标为开放问题或省略。
5. 同步标准 Markdown 链接、相关目录 `index.md` 和适用的 `log.md`。为每个 concept 填写真实 provenance；不要复制大段代码。
6. 运行结构校验和仓库级检查。所有修改的 concept、索引、日志和链接均已核对后才算完成。

## 重组与 Lessons

重组前写出目标 taxonomy。尽量保留相对路径；路径变化时更新所有入链、索引与来源路径，并在对应 `log.md` 顶部记录变更。

用户纠正了可复用的代理行为时，按仓库规则把简短、行动导向的规则写入 `context-kg/tasks/lessons.md`。

## 校验

运行随附脚本：

```bash
python3 ~/.codex/skills/knowledge-maintainer/scripts/context_kg_lint.py ./context-kg
```

脚本检查 OKF v0.2 的 concept frontmatter、必填 `type`、可选字段结构、保留文件格式、索引链接和日志日期顺序。缺少可选索引或存在断链会报告警告，不会被误判为 OKF 不合规。随后运行与改动相关的仓库检查，例如 `git diff --check`。
