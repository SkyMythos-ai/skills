# OKF 页面契约、索引与一等工程知识

写入、校验或讲解 `context-kg/` 页面格式时读取。权威格式以 [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) 为准；本页是本技能更严格的生产者约定。仓库 `AGENTS.md` 与 `context-kg/_meta/schema.md` 可以追加项目约束，冲突时说明并优先产出 OKF 合规内容。

## Concept 页面

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
- `status` 只使用 `draft`、`stable`、`deprecated`；缺失等同 `stable`。`deprecated` 只用于仍有审计、迁移或兼容价值而被有意保留的历史 concept，不替代删除无价值的废弃内容。
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

## 一等工程知识

测试用例、测试用例编码规范和代码设计规范是独立的一等 concept，不能只作为缺陷复盘、测试策略、ADR、任务记录或源码注释的附属段落。仓库 schema 未指定位置时使用以下入口；“独立”指每个适用范围有唯一权威 concept，而不是把所有模块和场景堆进一个巨型文件：

- **测试用例**：`quality/test-cases/` 下使用 `type: Test Case`。一个可独立演进的场景或紧密相关的参数组对应一个 concept，至少写明目标或需求链接、适用范围、前置条件、输入或步骤、预期结果、边界变体、覆盖状态及证据。Test Case 表达“要验证什么”；自动化测试表达“如何执行验证”，存在时链接测试文件或测试标识，不复制测试实现。没有自动化的稳定 case 明确标为 manual、planned 或 uncovered；自动化映射或测试代码变更本身也不等于验证通过，只有成功执行证据才能写入 `verified`。
- **测试用例编码规范**：默认权威入口为 `quality/standards/test-case.md`，使用 `type: Test Case Standard`。按产品域、测试层级或模块需要拆分时，用 `quality/standards/` 索引多个独立 concept。写明适用范围、case ID 编码、命名、粒度、必填字段、优先级、标签、自动化映射、例外条件、可执行检查和权威来源；它约束“测试 case 如何表达和管理”，不替代测试策略或具体 case。自动化测试代码约定只有在确有独立生命周期时才另建 `type: Test Code Standard`。
- **代码设计规范**：默认权威入口为 `technical/standards/code-design.md`，使用 `type: Code Design Standard`。按语言、架构层或模块拆分时维护目录索引。写明适用范围、设计约束及强度、理由、例外机制、验证方式和权威来源；ADR 记录一次决策及取舍，设计规范表达持续生效的工程约束，两者用标准 Markdown 链接关联。

这三类知识都执行[生命周期对账](lifecycle-and-write.md#生命周期对账)。产品规则变化时同步核对 Test Case 与自动化测试；测试用例编码规范变化时核对 case、索引和相关管理工具；代码设计规范变化时核对受约束实现、架构测试和关联 ADR。现有 case、代码或测试偏离已批准规范时，把偏离记录为缺陷、技术债或待迁移项，不把偏离事实静默改写成新规范。规范允许的例外必须限定适用范围、依据和期限，并链接权威规范。完全失效且无回归、审计、迁移或兼容价值的旧 case 和旧规范按生命周期规则删除。