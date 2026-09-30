# personal-development 使用指南

该技能覆盖功能实现、缺陷修复、重构、模块/API 设计、代码审查、工作区管理和开发任务交接，将开发流程、协作边界、编码规范与验证要求集中维护。通用准则适用于各语言，Go、Rust、Java 另有惯用法和可执行的 bad/good 案例。纯翻译、闲聊和非开发任务不适用；仅部署时读取流程与验证要求，不加载编码案例。

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

Agent 先读取开发流程，再按任务读取工作区协作、通用准则、语言规范、案例、注释规范或质量门禁。新增、修改或审查 Go CLI 时会读取 Cobra 规范；仅部署、工作区管理与交接不加载语言案例。项目约定和本次用户要求优先于个人默认；既有稳定代码无需为了统一风格而整仓重写，技能也不自动授权提交、推送或部署。

## 维护入口

- [SKILL.md](../skills/personal-development/SKILL.md)：触发范围、读取路由及完成标准。
- [开发流程](../skills/personal-development/references/development-workflow.md)：调查、计划、实施、验证和交付。
- [工作区协作](../skills/personal-development/references/workspace-collaboration.md)：改动边界、开发交接与 worktree 管理。
- [通用准则](../skills/personal-development/references/core.md)：跨语言规则。
- [Go CLI](../skills/personal-development/references/go.md#go-cli)：Cobra 命令树、参数与退出边界。
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

脚本需要所选语言的工具链；Java 案例要求支持 Java 17。缺失工具链会报告未验证并以状态码 2 退出，不能视为通过。bad 案例仅编译，good 案例还会执行断言；这些教学案例不替代实际项目集成测试。
