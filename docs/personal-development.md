# personal-development 使用指南

该技能覆盖功能实现、缺陷修复、重构、模块/API 与企业前端设计、代码审查、工作区管理和开发任务交接，将流程、编码规范、UI/UX 与验证要求集中维护。通用准则适用于各语言；Go、Rust、Java 有可执行的 bad/good 案例，React 前端有编码约定与教学片段。纯翻译、闲聊和非开发任务不适用；仅部署时读取流程与验证要求，不加载编码案例。

## 安装

在本仓库根目录安装到 Codex：

```bash
npx skills add . --skill personal-development --agent codex --global --yes
```

移除 `--global` 可安装到当前项目。仓库中的旧技能已由 `personal-development` 替代；若使用环境仍安装着旧技能，需在该环境移除旧副本并安装新技能。安装后开启新会话，使 Agent 重新发现技能。

## 典型用法

```text
使用 $personal-development 实现这个功能，保持项目现有契约，并运行对应检查。
```

```text
使用 $personal-development 审查当前改动，区分正确性缺陷和设计偏好。
```

```text
使用 $personal-development 解释错误处理规范，给出最小 bad/good 对照及适用边界。
```

```text
使用 $personal-development 检查当前工作区并创建开发交接，保留已有未提交改动。
```

```text
使用 $personal-development 实现这个企业控制台页面，采用 React + Tailwind CSS + shadcn/ui，兼顾首次使用与高频操作，并验证相关可用性原则和真实浏览器交互。
```

Agent 先读取开发流程，再按任务读取工作区协作、通用准则、语言规范、案例、注释规范或质量门禁。新增、修改或审查 Go CLI 时读取 Cobra 规范；前端实现与审查读取前端编码及企业 UI/UX，纯页面设计只需企业 UI/UX。新建且未指定技术栈的企业 Web 前端默认采用 TypeScript + React + Tailwind CSS + shadcn/ui，已有项目沿用实际技术栈。

企业 UI/UX 将尼尔森十大原则转为任务、状态、错误恢复等检查点，结合渐进披露降低上手成本，并保留高级能力入口。控件优先复用项目内部组件和 shadcn/ui，通过组合与变体扩展；自定义控件明确分层、接口、视觉/交互合同与内部复用边界。启发式走查、代码门禁、浏览器行为与真实业务验收分别留证。仅部署、工作区管理与交接不加载语言案例；项目约定和本次用户要求优先，技能不自动授权迁移、提交、推送或部署。

## 维护入口

- [SKILL.md](../skills/personal-development/SKILL.md)：触发范围、读取路由及完成标准。
- [开发流程](../skills/personal-development/references/development-workflow.md)：调查、计划、实施、验证和交付。
- [工作区协作](../skills/personal-development/references/workspace-collaboration.md)：改动边界、开发交接与 worktree 管理。
- [通用准则](../skills/personal-development/references/core.md)：跨语言规则。
- [Go CLI](../skills/personal-development/references/go.md#go-cli)：Cobra 命令树、参数与退出边界。
- [前端编码](../skills/personal-development/references/frontend.md)：TypeScript、React、Tailwind CSS、shadcn/ui、组件选型与内部复用。
- [企业 UI/UX](../skills/personal-development/references/enterprise-ui.md)：上手成本、信息架构、尼尔森十大原则与浏览器验收。
- [企业 UI 经验案例](../skills/personal-development/references/cases-enterprise-ui.md)：结合 Fusion、MaaS、Pole 的高度/滚动、真实几何、浮层、查询、原型与预览经验，保留来源和适用边界。
- [案例索引](../skills/personal-development/references/cases.md)：按问题选择正反案例。
- [质量门禁](../skills/personal-development/references/quality-gates.md)：检查与执行合同。
- [本地环境检查](../skills/personal-development/references/local-checks.md)：工具探测和环境准备。

以仓库中的 `skills/personal-development/` 维护流程、规范与案例，修改后重新安装以更新使用环境。仓库改动不会自动同步到已安装副本。

## 验证与排查

在仓库根目录编译所有语言案例并执行 good 案例断言：

```bash
python3 skills/personal-development/scripts/verify_examples.py
```

只验证某种语言，或对 Go 启用竞争检测：

```bash
python3 skills/personal-development/scripts/verify_examples.py --language go --race
```

脚本仅覆盖 Go/Rust/Java，需要所选语言的工具链；Java 案例要求支持 Java 17。缺失工具链会报告未验证并以状态码 2 退出，不能视为通过。bad 案例仅编译，good 案例还会执行断言；这些教学案例不替代实际项目集成测试。前端教学片段按目标项目的类型/构建与行为检查验证，页面设计和交互再完成真实浏览器走查。
