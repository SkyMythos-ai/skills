---
name: personal-development
description: 应用个人开发流程与工程规范，覆盖实现、修复、重构、模块/API 设计、企业前端 UI/UX、代码审查、工作区管理及开发交接；按需读取流程、语言规范、可用性与验证要求。纯翻译、闲聊和非开发任务不适用；仅部署时不加载编码案例。
---

# 个人开发规范

目标：在授权范围内完成开发工作，保护已有改动，保持职责与契约清楚，以真实检查支持交付结论。

## 路由

先读取[开发流程](references/development-workflow.md)，核对本次范围、项目约定和验收入口；已在当前上下文读取且未变化的内容复用。以下材料按任务读取，不全量加载。

| 触发条件 | 读取内容 |
| --- | --- |
| 修改文件、暂存/提交、管理 worktree 或创建开发交接 | [工作区协作](references/workspace-collaboration.md)，只执行对应操作的规则 |
| 实现、修复、重构、模块/API 设计或代码审查 | [通用编码准则](references/core.md)及涉及语言的 [Go](references/go.md)、[Rust](references/rust.md)、[Java](references/java.md)、[前端 TypeScript/React](references/frontend.md)；其他语言按通用准则及项目/语言惯例处理 |
| 前端页面/组件实现、交互修复或审查 | [前端编码](references/frontend.md)与[企业 UI/UX](references/enterprise-ui.md)，按当前问题选择[前端案例](references/cases-frontend.md) |
| 新增、自定义、提取或修改共享前端控件 | [组件选型与内部复用](references/frontend.md#组件选型与内部复用)，先复用内部与 shadcn/ui 控件，再明确自定义合同及调用方验证 |
| 企业软件页面规划、信息架构或 UI/UX 设计评估 | [企业 UI/UX](references/enterprise-ui.md)，覆盖上手成本、渐进披露与尼尔森十大可用性原则；涉及代码时再读前端编码 |
| 既有企业产品改版、原型转实现，或抽屉/导航/查询/预览问题 | 按问题选择[企业 UI 经验案例](references/cases-enterprise-ui.md)，核对触发、边界与行为证据，不照搬项目组件库、设备范围或固定尺寸 |
| 新增、修改或审查 Go CLI | [Go CLI](references/go.md#go-cli) |
| 代码实现与审查、规范讲解或编码规则更新 | 从[案例索引](references/cases.md)选择相关完整案例，不照搬业务策略 |
| 关键接口、状态、并发/幂等/降级设计，或注释编写与审查 | [注释规范](references/comments.md) |
| 代码审查 | [审查清单](references/review.md)，同时检查调用方；问题附位置、触发、影响和改法，区分偏好与缺陷 |
| 新项目、工具链/CI 变更、门禁缺失或失败、质量策略设计 | [质量门禁](references/quality-gates.md)，核对实际 formatter、lint、编译与测试入口 |
| 工具首次使用、环境变化、启动失败或询问本地可执行性 | [本地检查](references/local-checks.md)，按需运行 `scripts/probe_tools.py`；工具能启动后仍需执行项目真实门禁 |

仅部署、工作区管理和开发交接任务不加载语言案例。非开发任务的交接由相应任务流程处理。本 Skill 不自动授权重构、迁移、提交、推送或部署。

## 编码与规范维护

- 编码前说明职责、契约、失败语义和验证方式；简单修改可用一句话完成，不为套用流程生成架构文档。
- 实现围绕领域动作组织状态、资源和副作用；重构先固定外部行为及不变量，再调整边界并清理本次替代路径。小方法、接口、DDD、状态机按收益采用，不机械拆分或要求存量整仓对齐。
- 新增非显然编码规则提供场景、bad、问题、good、改善点、边界与验证；沿用案例 ID，小改动只完善相关例子。用户要求讲解规则时，在答复中展示最小 bad/good 对照并说明原因与边界。
- 案例是教学程序或标明的伪代码；缩短时保留结论所需前提，省略实现就收窄保证。未示范的认证、持久化和分布式原子性由项目实际证明。
- 修改 Go/Rust/Java 案例后运行 `python3 scripts/verify_examples.py`，可用 `--language go`、`rust` 或 `java` 限定范围；它只编译 bad、编译并执行 good 断言，不证明生产集成。缺失工具链标为未完成。前端案例是教学片段与设计对照，按[前端验证](references/frontend.md#验证)使用目标项目工具链，不由此脚本验证。
- Go 并发案例可加 `--race`；缺 JDK 时可用 `--java-image <已在本地的JDK镜像>`。容器只挂载临时案例目录、禁用网络且不自动拉取镜像。

## 维护边界

`references/` 是开发流程、协作规则和编码案例的正文来源；全局 AGENTS.md 只保留通用操作边界与 Skill 触发。项目例外记录条目、范围、原因和替代保证，普通技术选择无需反复确认。长期 memory 仅保存稳定偏好和入口，修改仍须用户明确要求。
