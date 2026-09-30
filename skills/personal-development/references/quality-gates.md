# 语言检查与硬质量门禁

目录： [职责](#职责) · [执行合同](#执行合同) · [Go](#go) · [Rust](#rust) · [Java](#java) · [Sonar](#sonar) · [存量与例外](#存量与例外) · [接入验收](#接入验收)

本规范的全局默认是：**可机械验证的规则应进入版本化配置和 CI，已启用的必需门禁失败就阻断交付。** 编码任务先核对项目真实配置；新项目及明确的门禁接入任务按本文落地。已有项目缺少检查时记录具体缺口，在相关范围增量接入，不借一次局部修复改造全部仓库或擅自开通外部服务。

## 职责

| 层次 | 检查什么 | 默认处理 |
| --- | --- | --- |
| Formatter | 缩进、布局、导入顺序 | 一套主格式规则；CI 检查，不悄悄修改代码后报成功 |
| 编译器 / 类型检查 | 类型、依赖、语言约束、支持的构建组合 | 全部必需组合通过，不能用增量 lint 代替 |
| 语言 linter | 错误处理、可疑逻辑、资源、语言惯用法 | 明确启用规则；违规返回非零 |
| 测试 | 接口行为、状态、故障、并发与兼容合同 | 按项目风险执行；失败与应运行却未运行均不可报通过 |
| 依赖 / 安全扫描 | 已知漏洞与项目安全策略 | 按项目策略独立配置，普通 lint 不代表完成审计 |
| Sonar | 静态分析、覆盖率/重复度等指标与统一质量判定 | 接入后等待 Quality Gate；不替代原生工具和测试 |
| 设计审查 | 职责、真实 Why、input → output 是否正确、业务取舍 | 保留人工/代理审查及行为证据，不能由“注释率达标”代替 |

函数长度、复杂度与重复率可用于发现候选；默认不以统一数字迫使所有语言拆碎方法。确需硬阈值时，在项目记录规则、适用对象和例外。规则集以可解释、低噪声为起点，不默认启用所有检查。

## 执行合同

- 本地环境按[准备、探测与真实执行](local-checks.md)逐层验收：先核对可复现版本和实际启动，再验证项目配置/依赖并执行门禁；工具缺失按项目 setup 补齐，不能只检查 PATH。
- 本地与 CI 复用仓库内同一检查入口及配置，使用固定的工具链、插件和 linter 版本；版本升级是可审查变更，不使用浮动 `latest`。
- IDE 和 pre-commit 方便早发现；CI 是权威执行点。完整的合并阻断还需远端 required checks / ruleset，检查对象必须对应本次提交或平台要求的合并提交。
- 必需检查不得 `|| true`、`continue-on-error`、忽略退出码或仅上传报告。Bash 经 `tee` 留日志时保留 `pipefail`。报告上传可在失败后继续，但不能覆盖原失败状态。
- 超时、工具缺失、配置无效、扫描取消、分析失败和预期报告缺失均是未通过；记录实际原因，不伪装成发现业务缺陷或零问题。
- 检查范围明确到 module/workspace、target、features/build tags、测试及生成代码策略；多模块逐一覆盖，不把从根目录执行一次当作全仓已覆盖。
- 每次新接入或改变门禁，使用已知违规样例证明会阻断，再修复样例证明会通过；不要只看成功日志。行为链为 `违规输入 → 检查非零 → CI 失败 → 合并受阻`，各层分别留证。

### Q1：错误不能被日志管道吞掉

场景：已安装项目固定版本的 golangci-lint，以下片段由 Bash 执行，工作目录与配置正确。

**Bad**：即使 linter 失败，通常也只返回 `tee` 的成功状态。

<!-- gate-example: shell-bad -->
```bash
set -eu
golangci-lint run ./... 2>&1 | tee lint.log
```

**Good**：保留诊断日志，同时传播检查失败。

<!-- gate-example: shell-good -->
```bash
set -euo pipefail
golangci-lint run ./... 2>&1 | tee lint.log
```

执行合同：`linter exit 1 + tee exit 0 → Bad exit 0 / Good exit 1`；`两者 exit 0 → Good exit 0`；日志写入失败也必须失败。若不用管道，可直接执行检查命令；本例只证明 shell 退出码传播，不证明 CI 或远端规则已生效。

## Go

默认组合：`gofmt` + `golangci-lint` + 编译/测试；并发代码补适用范围的 race。优先保留现有工具链，无配置时以下是 **golangci-lint v2 的最小起点**，不是要求覆盖已有规则集。

<!-- gate-example: golangci-config -->
```yaml
version: "2"
run:
  timeout: 5m
  issues-exit-code: 1
  tests: true
linters:
  default: none
  enable:
    - govet
    - staticcheck
    - errcheck
    - ineffassign
    - unused
    - nolintlint
  settings:
    nolintlint:
      require-explanation: true
      require-specific: true
  exclusions:
    generated: strict
formatters:
  enable:
    - gofmt
  exclusions:
    generated: strict
issues:
  max-issues-per-linter: 0
  max-same-issues: 0
```

落入项目 `.golangci.yml` 后，逐个 module 执行 `golangci-lint config verify`、`golangci-lint run ./...`、`go test ./...`，生产构建参数不同则补对应 `go build`。`run` 检查已启用的 formatter，CI 不加 `--fix`；本地可用 `golangci-lint fmt` 修复。配置版本 `2` 不是二进制版本锁定，仍需选择兼容项目 Go 版本的固定工具版本。[配置](https://golangci-lint.run/docs/configuration/file/)、[CLI](https://golangci-lint.run/docs/configuration/cli/)

增加资源关闭、context 传播、错误链等规则时，先验证真实误报与整改成本，再逐条提升为门禁。`nolintlint` 要求明确规则名和解释；不要以目录级忽略消除真实问题。

## Rust

默认组合：`rustfmt` + `Clippy` + `cargo test`。遵从项目 `rust-toolchain.toml` 与支持矩阵。下面检查默认 feature 集；需要其它组合时逐一执行项目矩阵，不声称这几条覆盖所有配置。

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

`-D warnings` 将 Clippy 与编译器 warning 变为失败；`pedantic` 按规则评估，`restriction` 不整组开启。项目已要求 `--all-features` 时遵守；互斥 feature 项目必须按组合检查。[Clippy 官方用法](https://doc.rust-lang.org/clippy/usage.html)

依赖审计可按项目策略独立采用 cargo-audit / cargo-deny；记录工具版本、策略与数据库新鲜度。不能把 fmt/Clippy 通过称为安全审计完成，也不把特定 Gateway 的全部参数复制到所有 Rust 项目。

## Java

默认选用项目 Maven/Gradle wrapper；格式工具与代码规则分工明确，例如已有 Spotless 负责格式、Checkstyle 负责约定，SpotBugs 负责字节码缺陷。避免几个工具维护互相冲突的格式配置；PMD / Error Prone 按实际收益增加。

### Q2：报告插件需要绑定失败检查

**Bad**：只在 `<reporting>` 中配置 SpotBugs，或只生成 HTML，再把 `./mvnw verify` 的成功当作静态检查通过。

```xml
<reporting>
  <plugins>
    <plugin>
      <groupId>com.github.spotbugs</groupId>
      <artifactId>spotbugs-maven-plugin</artifactId>
      <version>${spotbugs.version}</version>
    </plugin>
  </plugins>
</reporting>
```

**Good**：在 `<build><plugins>` 中绑定 `check`。以下是 POM 插件片段，`${spotbugs.version}` 必须在项目属性中固定为与 JDK 兼容的确切版本，不是可直接运行的完整 POM。

<!-- gate-example: spotbugs-plugin -->
```xml
<plugin>
  <groupId>com.github.spotbugs</groupId>
  <artifactId>spotbugs-maven-plugin</artifactId>
  <version>${spotbugs.version}</version>
  <configuration>
    <failOnError>true</failOnError>
    <includeTests>true</includeTests>
  </configuration>
  <executions>
    <execution>
      <id>quality-check</id>
      <phase>verify</phase>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>
```

输入输出：`已编译的违规类 → 命中已启用规则 → check 失败 → verify 非零`。有效 POM 中还需核对 include/exclude、threshold、skip 属性与激活 profile，避免片段看似存在却未执行。[SpotBugs 构建门禁](https://spotbugs.github.io/spotbugs-maven-plugin/examples/violationChecking.html)

Checkstyle 使用 `checkstyle:check` 并保留 `failOnViolation=true`；Gradle 对应任务需进入 `check` 依赖且不忽略失败。验证真实任务日志和多模块覆盖，不能仅由任务名推断启用。单元测试与集成测试也须分别确认绑定；JaCoCo 等报告存在不等于已施加覆盖率约束。[Checkstyle check](https://maven.apache.org/plugins/maven-checkstyle-plugin/check-mojo.html)

## Sonar

是否采用 Sonar、采用哪种版本/部署方式，由项目已有基础设施与授权范围决定；全局强制的是有效质量门禁，不要求每个仓库使用同一商业平台。接入前核实目标版本的语言、PR 分析、报告导入和权限支持，避免假定所有语言功能一致。

### Q3：上传成功不是质量达标

**Bad**：只执行扫描上传，就按 scanner 上传成功允许交付。

```bash
sonar-scanner
```

**Good**：项目参数、凭据和报告均已正确配置时，等待服务器计算完成；参数同样可传给项目使用的 Maven/Gradle scanner。

```bash
sonar-scanner -Dsonar.qualitygate.wait=true -Dsonar.qualitygate.timeout=300
```

输入输出：`有效分析 + Gate FAIL → 检查失败`；`上传完成 + 仍在计算 → 等待`；`超时/无法获取结果 → 未通过`；只有正确分析对象的通过结果可满足此门禁。若 CI 已有等价的等待 action/webhook 步骤，可复用该步骤；不能同时省略两种等待。[官方等待参数](https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/analysis-parameters/parameters-not-settable-in-ui)

覆盖率由实际测试产生并导入；核对报告匹配本次源码、模块与路径。个人建议从“新代码无新增已启用规则问题”开始；覆盖率、重复度阈值由项目明确。若采用 Sonar way，核对实例当前阈值以及小改动豁免设置，不能口头说“每个 PR 必须 80%”而实际不足阈值行数被豁免。PR gate 只看适用的新代码条件，存量风险仍要有全量跟踪。[Quality Gate 条件与小改动机制](https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates)

## 存量与例外

- 新项目直接从最小规则集建立硬门禁。存量项目先运行全量扫描固定债务基线，新增违规阻断，旧问题有责任人与整改计划；不在一次业务改动里机械扫全仓。
- 增量 lint 必须固定 PR 目标分支与基线提交，取到足够 Git 历史。Go 可从目标分支 merge-base 过滤新问题；不要用依赖 dirty 状态的 `--new` 充当确定性 CI 基线。[增量参数](https://golangci-lint.run/docs/configuration/cli/)
- 增量过滤可能漏掉在未改行上暴露的缺陷；类型/编译、项目必需测试与关键安全检查不因增量模式被关闭。保留全量扫描及基线比较，按项目节奏追踪存量，不用定期全扫替代本次必需检查。
- 误报豁免限定到具体规则和最小作用域，写明原因、证据、责任人及复查日期或明确退出条件。规则确不适用于项目时在配置中说明；不为过 CI 临时关闭整组规则、抬阈值或重置基线。
- 生成/第三方代码可明确排除；自有测试代码默认参与检查。覆盖率排除需有真实理由，不能通过删除断言、排除复杂模块或新增无意义测试制造达标。
- 其他语言遵循相同层次：采用该项目成熟的 formatter、类型检查、linter 与测试组合，按实际版本验证命令，不生搬三种语言的工具名称。

## 接入验收

1. 记录工具/插件版本、规则配置、范围、基线、新代码阈值与例外；给出本地和 CI 的共同入口。
2. 在隔离样例或专用验证分支制造格式错误、至少一项真实 lint 违规、失败测试，证明对应检查非零；修复后同条件转绿。验证缺工具/超时也不会变绿。
3. 接入 Sonar 时用本次分析的标识核对实际 Gate 状态、报告与提交匹配；不能用 shell 替身结果冒充 Sonar 集成通过。
4. 在获授权的远端接入任务里，核对 required checks、路径过滤、条件跳过、fork PR 与合并队列等适用触发条件；必需 job 被跳过不得让总门禁返回通过。用失败检查验证实际合并受阻，或明确报告尚未验证。
5. 交付分开报告 **规范已定义 / 项目已配置 / CI 已运行 / 远端已阻断**。本个人 skill 更新只定义规范，不宣称已替每个仓库启用 CI、采购 Sonar 或修改分支保护。
