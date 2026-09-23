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
