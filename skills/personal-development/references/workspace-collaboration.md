# 工作区协作

按当前操作读取对应小节。普通编码不扫描全部 worktree，也不自动创建交接文件。

## 改动与 Git 边界

- 修改前检查相关工作区状态，保留已有 dirty/untracked 和并行任务改动。暂存、提交仅包含本任务内容；用户授权某项操作不自动授权提交、推送或部署。
- 写入同一工作区的协作任务明确文件归属；发现并行变化先重新核对，避免覆盖。不能可靠区分本任务改动时，先缩小操作边界。

## 开发任务交接

- 创建或更新 handoff 时放当前项目根目录 `.handoff/`；无 Git 项目时放 workspace 根目录。此位置覆盖交接 Skill 的系统临时目录默认值。
- 文件名使用日期和主题；引用已有 ADR、任务、Issue、提交及 diff，不重复复制。移除账号口令、Token、API Key、数据库密码、个人信息和其他敏感内容。
- `.handoff/` 是本地协作资产，禁止暂存、提交和推送。Git 项目优先写入 `.git/info/exclude`，不通过提交 `.gitignore` 扩散个人目录约定。
- 完成前执行 `git check-ignore -v .handoff/<file>` 和 `git status --short --untracked-files=all`，确认交接文件不会进入 Git。

## Git linked worktree

- 仅创建、迁移、修复或清理 worktree 时执行本节。默认存放主项目 Git 根目录 `.worktree/`，用户明确指定其他位置时遵从；目录使用可辨识的任务或分支语义名称。
- 使用 `git worktree add`、`move`、`repair` 等 Git 原生命令管理，不用普通复制、移动或删除目录绕过管理记录。
- 创建或迁移前核对目标的 dirty/untracked、锁定及进程占用。不覆盖已有目录、不丢弃未提交改动、不擅自删除分支。
- `.worktree/` 是本地开发资产，禁止暂存、提交和推送；优先写入 `.git/info/exclude`，不为个人目录约定提交 `.gitignore`。
- 完成前执行 `git worktree list --porcelain`、`git check-ignore -v .worktree/<probe>`、`git worktree prune --dry-run --verbose` 和 `git status --short --untracked-files=all`，核对路径、忽略规则、管理记录与提交边界。
- 主仓或 worktree 曾被文件管理器、同步工具或普通目录复制/移动时，另扫描新旧父目录的同名或疑似目录，区分有效登记、未登记副本及独立改动。仅在内容完整保留且副本无独立修改时做可恢复清理。

## 示例：共享工作区

**场景**：修复文件 A，工作区已有另一任务对文件 B 的修改及未跟踪日志。

**Bad**：`git add .` 后提交，或清空工作区再开始；会混入或丢失无关改动。

**Good**：先检查状态，限定 A 的修改和暂存范围，核对 staged diff；B 和日志保持原状。需要隔离时按上述规则创建 worktree，而不是复制目录。

**验证关注点**：本任务 diff 与 staged diff 一致，无关改动仍完整；交接文件与 worktree 目录被本地排除。
