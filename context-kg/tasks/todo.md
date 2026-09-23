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

## 文档生命周期治理

- [x] 明确新旧方案冲突的识别依据与权威性排序
- [x] 为写入和重组流程增加合并、替换、删除的生命周期闭环
- [x] 规定废弃内容删除后的入链、索引、来源和日志清理要求
- [x] 同步使用指南中的知识库治理场景
- [x] 运行技能校验、单元测试、知识库 lint 与差异检查
- [x] 完成独立场景复核并记录结论

### 验收标准

- 新证据或新决策与既有 concept 冲突时，Agent 会先确定当前有效结论，而不是并列追加矛盾内容。
- 已被完全取代且不再承担审计、迁移或兼容价值的旧内容会从活动知识库删除；仍有历史价值的内容会从当前事实中隔离，并明确替代关系。
- 删除或重组后，所有相关索引、标准 Markdown 入链、`sources[].resource` 和适用日志均同步更新。

### 生命周期治理 Review

- Skill 新增“生命周期对账”，以适用范围、生效时段和知识角色识别冲突，不按文件新旧直接裁决。
- 已生效的新方案会替换活动知识中的旧结论；旧内容仅在仍有审计、迁移或兼容价值时以 `deprecated` 保留，否则在迁移有效独有内容后删除。
- 尚未生效的目标方案与当前实现可以并存，但必须明确角色和生效条件；证据无法裁决时收敛为一个 `draft` 或开放问题，不把任何候选冒充当前事实。
- 删除、合并、移动或替换后要求扫描入链和 `sources[].resource`，同步索引与日志，并搜索旧路径和旧结论残留。
- Skill quick validation、8 个 lint 单元测试、实际 `context-kg` lint、Python 编译和 `git diff --check` 均通过；独立四场景前向复核无阻断问题。

## 测试与工程规范知识化

- [x] 将可复用测试用例定义为独立、可追溯的知识类型
- [x] 将测试用例编码规范定义为独立权威 concept
- [x] 将代码设计规范约束定义为独立权威 concept
- [x] 明确三类知识与实现代码、自动化测试及生命周期对账的关系
- [x] 同步使用指南并完成场景复核
- [x] 运行技能校验、单元测试、知识库 lint 与差异检查

### 验收标准

- 测试用例不会被混写在缺陷复盘或测试策略中；每个可独立演进的 case 都有可检索、可验证的知识载体。
- 测试用例编码规范和代码设计规范分别拥有唯一权威入口，不与 ADR、任务记录或实现细节混杂。
- 代码、测试或规范变化后，相关 concept 会进行冲突收敛、替换或废弃清理，并保持证据和链接完整。

### 测试与工程规范知识化 Review

- 新增 `Test Case`、`Test Case Standard`、`Code Design Standard` 三类一等知识及默认渐进式入口；独立文档按可独立演进的 scope 划分，避免巨型文件。
- Test Case 表达“要验证什么”，自动化测试表达“如何执行验证”；自动化映射或代码变更不等于验证通过，`verified` 必须有成功执行证据。
- 测试用例编码规范覆盖 case ID、命名、粒度、字段、优先级、标签和自动化映射；自动化测试代码规范仅在存在独立生命周期时另建 concept。
- 代码设计规范保持规范性权威；现有实现偏离时记录缺陷、技术债或待迁移项，不用实现现状静默覆盖规范。
- 三类知识均执行生命周期对账；冲突未决时把主张、来源和 provenance 收敛到一个 `draft`，旧 case 或规范无剩余价值时删除。
- Skill quick validation、8 个 lint 单元测试、实际 `context-kg` lint、Python 编译和 `git diff --check` 均通过；独立模拟场景前向复核无规则层面的阻断或实质歧义。

## 快速检索、增量维护与会话摘要

- [x] 明确索引优先、候选定位、少量正文展开的快速检索路径
- [x] 定义候选排序、可信度判断和停止条件
- [x] 规定按变更影响面增量更新 concept、索引、链接和日志
- [x] 定义 Session Summary 的位置、内容契约和生命周期
- [x] 区分正式知识摘要与 `.handoff/` 临时交接资产
- [x] 同步使用指南并完成行为验证
- [x] 运行技能校验、单元测试、知识库 lint 与差异检查

### 验收标准

- 普通查询不会预载整库正文；先得到少量候选路径，再只读取足以回答问题的 concept 和证据。
- 普通写入只处理受变更影响的知识分支；仅在删除、移动、冲突治理或全库审计时扩大扫描范围。
- 会话摘要只记录目标、决定、知识变更、验证、未决项和下一步入口，不复制聊天或成为长期事实的第二权威源。
- 索引和摘要不会无限堆积或形成需要全量重建的易失缓存。

### 快速检索、增量维护与会话摘要 Review

- 检索流程已收敛为“根/分支索引 → 元数据候选 → 少量正文 → 必要的一跳证据”，并以子意图覆盖、结论唯一、状态时效可信和无未核验冲突作为停止条件。
- 新增无状态只读 `context_kg_search.py`，支持精确匹配奖励、中文多词跨字段、type/status/scope/limit 过滤、历史检索、限定范围正文回退和可解释评分；默认排除 deprecated 与 Session Summary。
- 元数据零命中时，只有真实非空 `--scope` 才自动读取该分支正文；全库正文搜索必须显式 `--body`。测试同时证明无 scope、`/` 和空白 scope 均不读取正文。
- 普通更新只处理目标 concept、直接关系、父索引和局部日志；删除、移动、合并、生命周期替换或 taxonomy/schema 变化才执行全库引用与旧结论扫描。
- Session Summary 按 `tasks/session-summaries/YYYY/MM/` 分层，索引最新在前，并提供 `--latest-session` 确定恢复入口；长期知识先回写权威 concept，摘要失去连续性价值后连同空月、空年入口清理。
- `.handoff/` 仅承载本地短期接管状态，不提交且不作为正式来源；Session Summary 是脱敏的时间点导航快照，普通领域查询默认排除。
- 14 个搜索行为测试与 8 个 lint 测试全部通过；Skill quick validation、实际 `context-kg` lint、Python 编译、真实检索冒烟和 `git diff --check` 均通过，独立 A-J 场景复核无阻断问题。

## 纳入 personal-coding-style

- [x] 核对本机技能资源、仓库布局与文档约定
- [x] 完整迁入技能并补齐目录和使用指南
- [x] 验证文件一致性、引用、技能格式及脚本
- [x] 记录检查结果并完成独立复核

### 验收标准

- `skills/personal-coding-style/` 包含原技能全部有效资源，仅调整本机路径以支持迁移。
- README 与 docs 索引可找到该技能，使用指南提供本地安装、调用和验证入口。
- 不改动本机已安装技能；验证结果区分通过与环境限制。

### personal-coding-style Review

- 完整迁入 17 个技能文件；与本机副本相比，仅 `core.md` 和 `local-checks.md` 的本机路径说明有差异。
- 独立复核确认资源完整、脚本按自身路径定位；两处本机路径依赖已清理。
- 根 README、docs 索引与独立使用指南已补齐，`npx skills add . --list` 成功发现两个技能。
- 技能 quick validation、68 个本地文件链接、两个 Python 脚本语法、知识库 lint 和差异空白检查均通过。
- Go/Rust 共 16 个案例编译通过，8 个 good 案例执行通过，无案例失败；本机 `javac -version` 失败，Java 案例未验证，整体案例脚本退出码为 2。
- 本机已安装技能保持不变，后续仓库改动需重新安装以同步。
