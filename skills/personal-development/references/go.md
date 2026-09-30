# Go 编码附录

与[通用准则](core.md)一起执行。适用版本以 go.mod、toolchain、CI 和部署环境为准。以下为个人风格与 Go 惯用法的结合；中文注释与模块组织属于个人默认。

## 1. 包、接口与类型

- 按职责组织 package，保持公开 API 精简；优先具体类型，接口在消费者需要隔离依赖时定义。接口按能力命名和收敛，不为每个 struct 配一个 interface。
- 用 struct 组合能力；嵌入类型前确认提升的方法是否应成为外部 API，避免偶然暴露依赖细节。包级可变状态与 init 副作用保持最少，依赖默认显式传入。
- 指针和值接收者按修改语义、复制成本和一致性选择。包含 mutex 等同步对象的值在使用后不应被复制。
- 明确 nil 指针、带类型的 nil interface、nil slice、空 slice 的边界差异；JSON 中 null 与 [] 按协议输出。避免把“不存在”与业务零值混为一谈。
- 导出声明用以名称开头的完整中文句子描述合同；关键设计说明原因，关键接口给出具体 input → output、错误及副作用，见[注释规范与 G2 示例](comments.md)。gofmt/goimports 与标识符惯例遵循项目配置。[Go 审查指南](https://go.dev/wiki/CodeReviewComments)

## 2. 错误与流程

- 错误路径先处理并返回，保持正常流程平直；error 应检查、传播或处理。普通失败返回 error，panic 保留给明确的程序不变量破坏等场景。
- 用 errors.Is / errors.As 判断错误，按需以 fmt.Errorf 和 %w 保留可检查的原因。是否暴露底层错误属于 API 决策，不能把实现细节偶然固化为合同。
- 默认返回具体的错误原因，避免每层重复包装相同文字或反复打印。明确可忽略的清理错误需要说明理由；写入或提交失败不能因发生在 defer 中就丢弃。[错误包装与 API 边界](https://go.dev/blog/go1.13-errors)

## 3. context、并发与资源

- 请求相关函数显式接收 context.Context，通常作为首参；默认不存入业务 struct，不用 context.Value 代替普通业务参数。
- 派生 context 的创建者负责调用 cancel；上下文沿调用链传播。确需后台继续执行时明确转交给监督者及其独立生命周期，不能随意用 Background 丢掉调用方取消。
- 每个 goroutine 明确谁启动、何时退出、谁等待和处理错误。channel 的关闭由能证明不会再发送的一方负责；消费者取消不能导致发送方永久阻塞。
- channel、mutex 与 atomic 按同步问题选择；普通共享状态用锁通常已足够，不为“更 Go”把所有逻辑改成消息循环。
- 获取资源成功后尽早安排释放；循环中多次 defer 会积累到当前函数返回，必要时提取一个有完整资源生命周期的小函数。[context 指南](https://go.dev/blog/context)、[并发任务生命周期](https://go.dev/wiki/CodeReviewComments#goroutine-lifetimes)

## 4. 验证

- 默认以 gofmt、golangci-lint、编译/测试建立机器门禁，具体 v2 配置、失败退出与增量基线见[Go 门禁](quality-gates.md#go)；项目已有配置优先，缺失工具不能报告为检查通过。
- 使用项目已有命令完成格式、编译、静态检查与测试；无专门入口时可从 gofmt 检查、go vet ./...、go test ./... 开始，在对应 module 范围内执行。
- 多个独立输入/输出案例适合表驱动测试；复杂状态机与时序用明确步骤表达，不强塞进巨大表格。外部测试包或包内测试按所需行为边界选择。
- 影响并发的变更运行适用范围的 go test -race；受工具链或平台限制时记录缺口。race detector 只能发现执行到的路径，不能把一次通过当作并发正确证明。[竞争检测器](https://go.dev/doc/articles/race_detector)

## 5. 具体案例

遇到以下问题时读取 [bad/good 完整代码及断言](cases-go.md)，结合场景合同和适用边界判断。

### 审查对照

| 可疑实现 | 期望处理 |
| --- | --- |
| UserServiceInterface 与唯一实现逐方法完全镜像 | 从实际消费者需要的能力判断接口是否有价值 |
| 请求内部随手创建 Background 并启动 goroutine | 明确取消传播，或转交有退出和错误处理的后台任务 |
| 比较 err.Error() 或把错误转为空集合 | 使用稳定错误类型/原因链，保留失败与有效空结果的区别 |
| 为减少重复把不同业务规则塞进巨型 options | 让各规则保留清楚的职责，只共享稳定的共同语义 |

<a id="go-cli"></a>

## 6. Go CLI：统一 Cobra

所有项目的 Go CLI 使用 `github.com/spf13/cobra` 组织根命令、子命令、帮助和参数。禁止直接使用标准库 `flag`，也不以独立 `pflag.FlagSet` 或 `switch os.Args` 替代命令树。约束针对自有 CLI，不要求修改第三方库或 Go 测试框架内部的 flag。

- 新增及本次触达的自有 CLI 必须对齐本节；未触达的存量命令单独记录迁移范围，不自动扩大本次改动。
- `cmd/<binary>/main.go` 只负责执行命令和最终退出；内部执行函数返回 error，资源清理完成后再由入口退出。
- 命令适配层持有 options 和 I/O，通过 `RunE` 调用执行函数；领域包接受类型化输入，不读取或改写 `os.Args`、不依赖 Cobra。
- 长参数使用 `--name`；迁移时同步检查启动器、镜像、部署参数与文档。确有兼容要求时在入口明确处理并验证，不保留第二套解析器。
- 原生 CLI/stdio 协议桥需要透传上游 argv 时，用 Cobra `DisableFlagParsing` 明确边界，保留上游 `--help` 等参数的原始语义。

**场景**：CLI 提供服务启动与离线渲染；帮助和错误参数不能触发监听、建库或写配置。

**Bad**：`switch os.Args[1]` 分发，在内部调用 `flag.Parse()`、改写 `os.Args`，失败时 `os.Exit(1)`。解析依赖全局状态，内部退出会跳过 defer 清理。

**Good**：`root.AddCommand(newServeCommand(), newRenderCommand())`；构造器创建独立 options，用 `cmd.Flags().StringVar(&opts.Output, "output", "", "输出目录")` 定义参数，`Args: cobra.NoArgs` 校验位置参数，`RunE` 调用 `render(cmd.Context(), opts, cmd.OutOrStdout())` 并返回错误；只有 `main` 决定退出码。

**改善与边界**：解析、编排、领域行为和退出各有归属；简单命令可在单个适配文件完成。旧二进制别名可以在进入命令树前加固定子命令前缀，不承担参数解析。

**验证**：执行实际命令树检查根/子命令 help、未知命令/flag、非法值和多余参数，验证无文件、网络或进程副作用。重复构造不共享参数；业务错误传播且清理执行。仓库门禁扫描自有 CLI 的标准库 flag 导入，以非零退出阻断回归。
