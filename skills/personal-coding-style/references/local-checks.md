# 本地检查的可执行性

本地可执行性需要逐层证明：**版本可复现 → 工具能启动 → 配置和依赖能加载 → 真实检查能完成 → 已知违规会失败**。只写命令、只检查 PATH、只运行 `--version` 都不能证明整条链完成。

## 三个职责明确的入口

项目已有任务系统时复用；新接入时提供等价的三个入口。下面是入口合同，不表示每个仓库已经有这些文件。

| 入口 | 输入 → 输出 | 行为 |
| --- | --- | --- |
| setup / bootstrap | 项目版本声明 + OS/CPU → 所需工具与依赖 | 可重复执行；安装固定版本，下载校验来源与校验和，已有匹配版本不重复安装 |
| doctor | 项目根目录 + 选定检查集 → 可执行状态、实际/预期版本、缺失项 | 实际启动工具，核对运行时、wrapper、配置与必需服务；失败退出并给出准备方法 |
| check / verify | 已就绪环境 + 本次源码 → 格式/lint/编译/测试结果 | 调用与 CI 相同的入口和配置；失败阻断，不边检查边改变源码或升级工具 |

不要在每个仓库增加一套新的框架；`make`、`just`、项目脚本、Maven/Gradle 等现有入口都可以承担这些职责。setup 负责准备，check 的正常执行不得依赖临时安装最新版本。首次拉取依赖可能需要网络；“可本地运行”不等于“离线可运行”，离线模式需要事先准备对应缓存。

## 版本和环境从项目读取

- **Go**：从项目 module/workspace 和 CI 核对实际 Go 版本及支持矩阵；`go.mod` 的最低版本声明不能单独代表精确环境锁定。golangci-lint 另行锁定二进制版本并核对支持的 Go 版本，不能把 `.golangci.yml` 中的 `version: "2"` 当作工具版本。安装到项目或用户工具目录，check 使用明确路径。[安装说明](https://golangci-lint.run/docs/welcome/install/local/)
- **Rust**：通过 `rust-toolchain.toml` 固定版本及 rustfmt/Clippy 组件。运行 `rustup show active-toolchain` 与实际 `rustc --version` 核对环境变量、目录 override 是否覆盖项目声明；组件可启动后才执行 Cargo 门禁。缺失组件按该固定工具链准备，不修改全局默认版本来迎合一个项目。[工具链优先级](https://rust-lang.github.io/rustup/overrides.html)
- **Java**：核对完整 JDK 的 `java -version` 和 `javac -version`，以及 wrapper 实际使用的 JVM；`JAVA_HOME` 与 PATH 不一致必须处理。优先项目 `./mvnw` / `./gradlew`，缺系统 Maven/Gradle 并不等于项目不能构建。wrapper 的发行版版本与校验信息纳入仓库，首次运行可能下载发行版；wrapper 也不能代替项目 JDK/toolchain 配置。[Maven Wrapper](https://maven.apache.org/tools/wrapper/)、[Gradle Wrapper](https://docs.gradle.org/current/userguide/gradle_wrapper.html)
- **Sonar**：先判断项目使用 CLI 还是构建工具 scanner；检查版本、配置、报告来源、服务器可达性及凭据注入，日志不输出凭据。安装 scanner 不代表有 Sonar 服务。允许把依赖服务的步骤分为 CI 专用，但必须标明“本地子集通过”，不能声称完整门禁通过。
- **容器替代**：已有开发容器/CI 镜像可用于复现，固定镜像摘要并确认 CPU 架构、挂载权限和所需工具；只有 JDK 的镜像不能自动提供 Maven/Gradle 静态分析插件。以同一源码、配置和命令执行，并明确结果来自容器。容器运行时及缓存同样需要 doctor。

原生依赖、链接器、证书、代理、私有包访问、测试容器/数据库和目录写权限按实际失败补充，不把所有语言工具和服务都变成每个任务的前置条件。Windows 使用对应 wrapper/脚本，不能假定 Bash 可用。

## 可复用的首层探测

Skill 提供 [probe_tools.py](../scripts/probe_tools.py)，仅使用 Python 3 标准库。从技能根目录调用，将 `--project` 替换为可信项目的路径，显式选择需要探测的语言或工具：

```bash
python3 scripts/probe_tools.py \
  --project /path/to/project --language rust --expect rustc=1.94.0 --expect cargo=1.94.0
```

这里的 1.94.0 是当前 ai-gateway 的实测示例；其它项目必须从自己的版本声明填写。可重复 `--language go` / `--language java`，也可额外传入 `--require cargo-audit` 或 `--require sonar-scanner`。Java 按显式 `JAVA_HOME/bin` 优先探测。

输出包含命令路径、真实版本、退出码和缺失提示。`exit 0` 仅说明选定工具能启动且显式 `--expect` 匹配；缺失、失败、超时或版本不符为 `exit 2`。未提供 `--expect` 的工具不声称已核对版本策略。脚本不安装工具、不自动运行仓库 wrapper、不执行扫描或上传；被调用的工具代理可能按自身机制下载工具链，严格离线预检应先检查项目管理器配置。

后续仍需项目 doctor 验证 wrapper、有效配置、依赖和服务，再执行真实 check。探测器没有内置所有项目的版本/矩阵，避免个人脚本成为第二份工具链配置。

### Q4：命令存在不等于可执行

**Bad**：macOS 可能有 `/usr/bin/java` 占位程序，但没有 JDK。

```bash
command -v java
```

**Good**：在已有版本选择环境中实际启动，再核对版本输出与项目预期；完整 JDK 还需编译器。

```bash
set -euo pipefail
java -version
javac -version
```

输入输出：`只有占位程序 → Bad exit 0 / Good 非零`；`正确 JDK → 两个版本命令成功`。后者只证明 JDK 可启动，wrapper 使用的 JVM 和插件绑定仍需独立核对，不能省略实际构建检查。

## 后续编码任务的执行规则

1. 优先读取项目版本声明及已有检查入口，选择此次必需检查；工具首次使用、环境变化或启动失败时进行探测，同一环境未变化不反复全量盘点。
2. 缺工具时按已有项目 setup 准备兼容且固定的版本；当前任务范围内可逆的用户/项目目录准备可自主完成。没有可信版本依据时先查项目和官方兼容信息，不随意安装 latest 或重配整机。
3. 对无须账号/付费/环境决策的已知缺口，继续完成准备并重试；只有具体外部条件无法满足时报告阻塞。必需工具缺失不能悄悄跳过；可选项按项目合同记录为未执行。
4. 执行真实门禁并保留命令、版本、范围和结果。新建/改动检查入口时，用隔离样例验证真实 formatter/linter/test 的失败与修复转绿；现有项目的正常迭代不必每次重复故障注入。
5. 验收清楚区分“工具可启动”“版本已匹配”“隔离样例通过”“项目门禁通过”。仅修订个人规范时不宣称已经给所有仓库创建 setup/doctor/check。
