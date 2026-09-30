# Rust 编码附录

与[通用准则](core.md)一起执行。先核对 rust-toolchain、edition、MSRV、features 与实际异步运行时；不为使用某个惯用法擅自升级工具链。

## 1. 模块、所有权与类型

- 默认保持私有或 pub(crate)，只公开必要接口。按职责划分 module 和类型，使用组合与 trait 表达真正的能力边界，避免照搬面向对象类层次。
- 只读访问优先借用，修改用独占借用，需要保留或转交任务时接收所有权。clone、Arc 与锁用于明确的所有权或共享需求，不用来掩盖尚未理清的数据生命周期。
- 常见只读参数可采用 &str、&[T] 等合适的借用视图；具体取舍以调用便利、性能和合同为依据。泛型静态派发与 dyn Trait 按可扩展性、代码体积与运行时选择需要决定。[API 灵活性指南](https://rust-lang.github.io/api-guidelines/flexibility.html)
- 用 enum 与 match 表达互斥状态；Option 表达缺失，Result 表达失败。容易混淆的 ID、单位或经校验数据按需使用 newtype；构造器维护不变量，收窄可修改字段。
- 保留项目现有 unsafe 禁令。新代码默认使用安全 Rust；确需 FFI 或底层 unsafe 时按项目边界集中封装并说明安全不变量，不以性能猜测作为引入理由。[参数验证指南](https://rust-lang.github.io/api-guidelines/dependability.html)

## 2. 错误、文档与析构

- 可恢复故障使用 Result，错误类型供调用者区分有意义的失败。应用编排边界可以采用项目已有的上下文错误容器；公共库与领域接口保留需要匹配的错误语义。
- ? 用于清楚地传播错误；转换时保留原因链与操作信息。生产请求路径的 unwrap/expect 必须有可审查的不变量依据；测试、原型或经证明的不可能失败场景分别对待。[Result 与 panic 的选择](https://doc.rust-lang.org/book/ch09-03-to-panic-or-not-to-panic.html)
- 公开 API 用中文 rustdoc 描述合同，存在相应行为时写 Errors、Panics 等章节；关键设计说明原因，input → output 包含借用/所有权、成功与失败后的状态，见[注释规范与 R1 示例](comments.md)。跨线程错误按使用场景满足 Send/Sync。这里的中文是个人约定，非 Rust 官方要求。[文档指南](https://rust-lang.github.io/api-guidelines/documentation.html)、[错误互操作性](https://rust-lang.github.io/api-guidelines/interoperability.html)
- Drop 用于可靠、轻量的释放，避免 panic。需要报告关闭错误、提交事务或异步等待时提供显式 close/shutdown/finish；不能把关键确认仅放在不能返回 Result 的析构中。[析构指南](https://rust-lang.github.io/api-guidelines/dependability.html)

## 3. 异步、取消与资源

- 在每个可能挂起的位置检查取消后的状态：已取出但未写回的数据、已申请的配额、部分外部副作用分别如何处理。取消不等于回滚。
- 创建后台任务时明确句柄、错误、取消与等待的管理者；不能假定丢弃 JoinHandle 就停止任务，具体语义查运行时文档。请求 future 被丢弃与其派生任务退出是不同问题。
- 缩短锁持有范围；跨 .await 持锁应有明确需求、使用适合的同步原语并验证死锁和取消行为。阻塞 I/O 或长 CPU 工作遵循运行时的阻塞任务策略。
- 优先用有父子生命周期的方式组合任务，退出时按合同取消或排空并等待；持久业务交给可恢复机制，不寄希望于析构执行异步工作。[异步并发组织](https://rust-lang.github.io/async-book/part-reference/structured.html)

## 4. 验证

- 格式检查及 Clippy 的 warning 必须按项目策略产生阻断；新项目默认 `-D warnings`，明确 feature/target 矩阵与固定工具链，见[Rust 门禁](quality-gates.md#rust)。
- 遵循项目实际门禁，通常包括 cargo fmt 检查、Clippy、单元与集成测试；公开示例适合时加入文档测试。
- 按受支持 feature 组合与 target 检查；若项目明确要求 --all-features 则执行，互斥 features 的库采用已定义的组合矩阵。
- 属性测试用于状态不变量、解析器和较大输入空间；并发模型或故障注入用于具体竞争风险，不能为形式引入整套工具。
- 本规范不会自动要求所有 Rust 项目采用当前 ai-gateway 的 crate 划分、Redis 合同或全部构建参数。

## 5. 具体案例

遇到以下问题时读取 [bad/good 完整代码及断言](cases-rust.md)，结合场景合同和适用边界判断。

### 审查对照

| 可疑实现 | 期望处理 |
| --- | --- |
| 多个 bool 表达互斥执行状态 | 使用带数据的 enum，并使状态转移可审查 |
| 为编译通过层层 Arc<Mutex<...>> 与 clone | 明确所有权与共享需要，收窄修改面 |
| 丢弃任务句柄后假定请求结束即任务结束 | 按运行时语义管理任务生命周期 |
| 在 Drop 中尝试关键异步持久化 | 提供可等待、可报告失败的显式终结接口 |

Rust API Guidelines 是语言社区的 API 设计指南，需结合目标场景使用，并非语言编译规则。
