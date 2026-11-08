# 变更记录

按 Skill 分节；每节条目分 **行为变化** / **文档** / **脚本** 三类。技能包版本对应 `skills/<name>/SKILL.md` 的 `version`，正文规范的版本以各文件首部声明为准。首次发布之前的变更以 git 历史为准，本文件不回溯补写。

## knowledge-maintainer

技能包版本：`1.6`

### 1.6 — 2026-10-21

**行为变化**

- 校验脚本缺 PyYAML 时短路，返回专用退出码 `3`，不再逐页误报「缺少非空 type」；`0`/`1`/`2` 的语义不变。
- `context_kg_govern.py apply` 新增 `--dry-run`（只读输出 diff 与按 op 的动作计数）与 `--expect-actions N`（断言批次规模）。
- `rebuild` 短指令只接受显式 `$knowledge-maintainer rebuild`，或前一轮已确认本技能的知识库治理意图；构建、镜像、CI 语境的同名命令不再触发本技能。
- 含 `delete`/`archive`/`move` 的批次，`apply` 前必须输出「路径 + 动作 + 理由 + 后继或承接目标」清单并取得用户确认；纯 `keep`/`update` 批次不要求。
- 触发范围增加负向说明：普通文档写作、代码实现与重构、构建/镜像的 rebuild、聊天摘要不适用。

**文档**

- `SKILL.md` 从 177 行压缩到 78 行，只保留操作路由、检索停止条件、默认目录、破坏性硬门、职责边界与按需指针；正文抽出到 `references/okf-contract.md`、`lifecycle-and-write.md`、`session-summary.md`。
- 检索隔离语义收敛为 `references/local-retrieval.md` 的「历史内容隔离语义」单点定义（含四种参数组合的语义表），其余位置改为引用。
- 宿主安装路径改为 `$SKILL_DIR` 占位，新增「路径约定」说明仓库内与已安装两种形态。
- `docs/knowledge-maintainer.md` 只保留适用与不适用、安装、典型提示词、预期目录、校验与排错，不再重复规范正文。
- 与 `personal-development` 互加职责归属：`context-kg/` 内部结构与保留文件格式归本 Skill，代码实现与提交边界归该 Skill。

**脚本**

- 新增 `scripts/check_repo.py`（仓库级静态校验）与 `.github/workflows/ci.yml`（单测、lint、check_repo、空白字符检查）。
- `context_kg_lint.py` 的 `load_frontmatter` 区分「无法解析」（`None`，调用方短路）与「空 mapping」（`{}`）。
- `docs/design` 提示改为 `--docs-design` 显式开启，默认不输出。
- QMD 版本收敛为 `context_kg_qmd.py` 中的 `QMD_VERSION` 常量。

## personal-development

技能包版本：`1.6`；规范正文 `references/core.md` 版本 `1.5`（生效 2026-10-01）。

### 1.6 — 2026-10-21

**行为变化**

- `quality-gates.md` 中 `golangci-config` 与 `spotbugs-plugin` 两处标记改为 `gate-fragment:`，明确声明不参与自动校验；可执行的 `shell-bad`/`shell-good` 由测试真实执行。
- 任务计划与 lessons 的格式规定退化为「记到哪里」，格式以 `knowledge-maintainer` 的项目任务入口为准。

**文档**

- `agents/openai.yaml` 补 `default_prompt`；README 与安装说明说明当前只提供 Codex（`openai.yaml`）元数据，其他宿主按 `npx skills` 实际能力使用。
- `local-checks.md` 的版本示例改为占位；`cases-enterprise-ui.md` 的精确行号与 commit 引用降级为「来源类型 + 合同 + 核对日期」并集中到文末来源附录。
- `cases.md` 增加体量与条数列，并给出「默认读 1 例」的加载预算。

**脚本**

- `verify_examples.py` 抽出 `collect_examples`，标记与代码块不匹配、未配对或 ID 重复时显式报错。
- 新增 `tests/`：`test_gate_examples.py`、`test_probe_tools.py`、`test_verify_examples.py`。