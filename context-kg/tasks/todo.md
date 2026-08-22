---
type: Task Plan
title: knowledge-maintainer：OKF 与渐进式加载
description: 记录 knowledge-maintainer 遵从 OKF、支持渐进式读取及完成技能更名的实施与验证。
tags: [context-kg, okf, skill]
status: stable
generated: { by: codex/gpt-5, at: 2026-08-22T00:00:00+08:00 }
---

# knowledge-maintainer：OKF 与渐进式加载

- [x] 查明 OKF 的权威格式、目录与读取约定
- [x] 审查现有技能和 lint 脚本与 OKF 的冲突点
- [x] 调整技能说明及必要的配套实现
- [x] 运行技能校验、脚本测试与差异检查
- [x] 完成独立审阅并修正问题

## Review

- 技能已切换到 OKF v0.2 页面、标准链接、分层索引和日志契约。
- 查询流程已限定为逐层索引导航；缺索引时只动态合成当前层，不递归预载全库。
- lint 已区分 concept 与保留文件，校验 `type`、provenance/trust/lifecycle 基本结构、Attested Computation `runtime`、索引与日志，并将断链和推荐索引缺失保留为 warning。
- 8 个行为测试、技能 quick validation、实际 `context-kg` lint、Python 编译和 `git diff --check` 均通过；独立复核无阻断项。

## 重命名为 knowledge-maintainer

- [x] 审计旧技能名的目录、frontmatter、UI 元数据与文档引用
- [x] 将技能完整重命名为 `knowledge-maintainer`
- [x] 验证新技能并确认旧名称无残留

### 重命名 Review

- 技能目录、frontmatter、标题、UI 元数据、默认提示、命令示例和知识库引用均已同步为 `knowledge-maintainer`。
- 旧目录不存在；全仓库排除 `.git` 后，旧技能名零命中。
- 新目录下 8 个测试、技能 quick validation、实际知识库 lint、Python 编译和 `git diff --check` 均通过。
- 独立审计确认没有遗漏；`context_kg_lint.py` 保留原名，因为它描述被维护的知识库格式。

## README 安装说明

- [x] 核对 `npx skills` 的仓库、技能、Agent 与全局安装参数
- [x] 在 README 增加 `knowledge-maintainer` 安装和调用示例
- [x] 验证 README 命令可发现本地技能并完成文档检查

### README Review

- README 已提供交互式安装、Codex 全局免确认安装、项目级安装提示和显式调用示例。
- `npx skills add . --list` 成功发现唯一技能 `knowledge-maintainer`。
- 技能 quick validation、实际知识库 lint 和 `git diff --check` 均通过。

## Skills 使用文档

- [x] 设计可随技能数量扩展的 `docs/` 文档结构
- [x] 为 `knowledge-maintainer` 编写详细场景与使用指南
- [x] 精简根 README，并链接到技能文档索引和详情页
- [x] 验证文档链接、命令示例和知识库格式

### Skills 文档 Review

- 根 README 已收敛为仓库入口、技能目录、安装命令和最短调用示例。
- `docs/README.md` 定义每个 Skill 对应独立详情页的扩展约定。
- `docs/knowledge-maintainer.md` 覆盖适用边界、安装、渐进式读取、六类典型工作流、目录结构、校验和常见问题。
- 三份 Markdown 的 9 个链接、8 个单元测试、技能 quick validation、实际知识库 lint 和 `git diff --check` 均通过。
