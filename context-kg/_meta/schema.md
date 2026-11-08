---
type: Knowledge Schema
title: 本仓库 context-kg 的最小 schema
description: 声明本知识库实际使用的分支、认知角色与历史归档位置，供渐进检索和全库治理按同一约定判读。
tags: [schema, taxonomy, governance]
status: stable
sources:
  - resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: OKF v0.2 规范
  - resource: /technical/standards/knowledge-bundle-governance.md
    title: 分类、命名与历史归档规范
---

# 本仓库 context-kg 的最小 schema

本页是本知识库的项目约定，不是 OKF 的硬性要求，也不强制其他项目照搬。没有 `_meta/schema.md` 时按知识维护技能的生产者默认约定工作；本页只声明本仓库实际使用的分支与归档位置，减少“该放哪”的重复判断。

## 使用的分支

| 分支 | 认知角色 | 说明 |
| --- | --- | --- |
| `technical/` | 架构、合同、持续规范、ADR、调研与执行证据 | 下设 `adr/`、`standards/`、`research/`；长期技术结论都收敛到这里 |
| `tasks/` | 任务计划、进度、Review 与 lessons | 只承载过程与接续信息，长期事实迁入 `technical/` |

本仓库当前不使用 `business/` 与 `quality/`：还没有业务领域模型或独立质量知识。确需新增时先在此表声明角色，再建目录与索引，不静默扩张。

## 历史归档位置

- 归档统一放在原角色目录下的 `archive/`，本仓库实际使用 `technical/archive/`。
- 归档页保留原文与适用时期，标 `status: deprecated`，并在正文开头给出替代方案链接；活动索引不把它表述为当前方案。
- 任意层级含完整 `archive` 路径分量的页面都不进入默认检索，需 `--history` 显式展开。

## 读取约定

- 根 `index.md` 声明 `okf_version`，其余目录索引不带 frontmatter。
- `log.md` 按 `## YYYY-MM-DD` 分组、最新在前，不写 frontmatter。
- 其它 `.md` 都是 concept，必须有可解析 frontmatter 和非空 `type`；`type` 允许本仓库自定义，消费者须容忍未知类型。