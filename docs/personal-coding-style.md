# personal-coding-style 使用指南

该技能将个人编码习惯应用到功能实现、缺陷修复、重构、模块/API 设计和代码审查。通用准则适用于各语言，Go、Rust、Java 另有惯用法和可执行的 bad/good 案例。纯翻译、闲聊和仅执行部署命令不适用。

## 安装

在本仓库根目录安装到 Codex：

```bash
npx skills add . --skill personal-coding-style --agent codex --global --yes
```

移除 `--global` 可安装到当前项目。安装后开启新会话，使 Agent 重新发现技能。

## 典型用法

```text
使用 $personal-coding-style 实现这个功能，保持项目现有契约，并运行对应检查。
```

```text
使用 $personal-coding-style 审查当前改动，区分正确性缺陷和设计偏好。
```

```text
使用 $personal-coding-style 解释错误处理规范，给出最小 bad/good 对照及适用边界。
```

Agent 先读取通用准则，再按语言与任务选择案例、注释规范或质量门禁。项目约定和本次用户要求优先于个人默认；既有稳定代码无需为了统一风格而整仓重写。

## 维护入口

- [SKILL.md](../skills/personal-coding-style/SKILL.md)：触发范围、执行流程及完成标准。
- [通用准则](../skills/personal-coding-style/references/core.md)：跨语言规则。
- [案例索引](../skills/personal-coding-style/references/cases.md)：按问题选择正反案例。
- [质量门禁](../skills/personal-coding-style/references/quality-gates.md)：检查与执行合同。
- [本地环境检查](../skills/personal-coding-style/references/local-checks.md)：工具探测和环境准备。

以仓库中的 `skills/personal-coding-style/` 维护规范与案例，修改后重新安装以更新使用环境。本次迁入保留本机已安装副本；仓库改动不会自动同步到该副本。

## 验证与排查

在仓库根目录编译所有语言案例并执行 good 案例断言：

```bash
python3 skills/personal-coding-style/scripts/verify_examples.py
```

只验证某种语言，或对 Go 启用竞争检测：

```bash
python3 skills/personal-coding-style/scripts/verify_examples.py --language go --race
```

脚本需要所选语言的工具链；Java 案例要求支持 Java 17。缺失工具链会报告未验证并以状态码 2 退出，不能视为通过。bad 案例仅编译，good 案例还会执行断言；这些教学案例不替代实际项目集成测试。
