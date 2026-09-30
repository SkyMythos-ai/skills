# Java 编码附录

与[通用准则](core.md)一起执行。版本以构建配置、toolchain 和部署 JDK 为准；使用新特性前核实正式或预览状态及框架兼容性。

## 1. 类、接口与对象

- 类围绕清楚的业务职责封装数据和行为，默认通过组合协作。接口表达稳定行为或替换边界，不为每个类机械建立 Interface/Impl。
- 依赖默认通过构造器显式传入；保持字段可见性最小，适合时使用 final。继承只用于稳定的可替换关系或框架合同，避免把 BaseService 变成多种业务的共享杂物箱。
- 简单数据载体可使用 record，在构造处校验不变量。record 自 JDK 16 正式提供，但只是浅不可变；含可变组件时在构造和访问边界使用适当的防御性复制，集合元素也需检查。[接口指南](https://dev.java/learn/interfaces/)、[record 指南](https://dev.java/learn/records/)、[版本说明](https://docs.oracle.com/en/java/javase/16/language/java-language-changes.html)
- 必需字段在边界验证；Optional 适合表达返回值可能缺失，是否用于字段或参数按合同和框架适配决定，不把 null、空容器和异常一律转换成 Optional.empty。
- 精确金额采用整数最小单位或 BigDecimal，并明确精度、舍入与币种；时间按语义选择 Instant、Duration 或带时区的表示，避免用含糊的 long/String 承担所有数据含义。

## 2. 方法、异常与资源

- 方法按业务动作命名，服务方法以小方法组合流程。Stream 适合清楚的数据转换；复杂分支、资源操作和副作用较多时使用普通循环，不为链式外观牺牲可读性。
- 已知业务结果可以用枚举或结果对象表达；异常传播保留 cause，并在能采取动作的边界处理。checked/unchecked 依据调用者恢复责任及既有 API 选择，不制定全局“一律转换”的规则。
- 捕获 InterruptedException 时优先传播或按取消合同终止任务；无法继续传播且并非明确消费中断的边界，应恢复中断标志再转换或返回，不静默吞掉取消信号。
- AutoCloseable 资源默认用 try-with-resources；关键提交结果仍显式确认。处理关闭失败时保留原始异常与 suppressed exceptions。[异常与资源指南](https://dev.java/learn/exceptions/catching-handling/)、[中断异常合同](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/InterruptedException.html)
- 中文 Javadoc 写清公开方法的设计原因、输入约束、返回、异常及线程安全；input → output 包含对象创建/修改后的状态与失败结果，见[注释规范与 J2 示例](comments.md)。库要求英文时按已记录的项目例外执行。

## 3. 并发与版本边界

- 共享可变状态选择锁、并发集合或原子类，核对复合操作是否仍需同步；final 字段不保证其引用对象线程安全。Executor、Future 和异步链有明确的关闭、超时、取消与失败观察方式。
- 虚拟线程适合大量阻塞等待的独立任务，JDK 21 起正式提供。按任务创建虚拟线程，不建立虚拟线程池；下游并发通过信号量等方式限制，不能用“线程便宜”推断外部资源无限。[JEP 444](https://openjdk.org/jeps/444)
- 虚拟线程不增加 CPU 密集计算的处理能力。同步阻塞导致 carrier 被占住的限制需按 JDK 版本判断：JDK 24 已改进 synchronized 导致的 pinning，不能机械把所有 synchronized 改成 ReentrantLock。[JDK 24 迁移说明](https://docs.oracle.com/en/java/javase/24/migrate/significant-changes-jdk-24.html)
- 结构化并发、模式匹配等能力按实际 JDK 核实；预览功能需有项目明确采用约定。普通代码无需为追随新特性更改整个运行环境。

## 4. 验证

- 将 formatter、Checkstyle/SpotBugs 等选定工具绑定到实际构建检查，不能只生成报告；核对插件版本、失败开关、profile 与模块范围，见[Java 门禁及 bad/good](quality-gates.md#java)。
- 使用仓库已有 Maven/Gradle wrapper、formatter、静态分析和测试入口。无专门入口时，按项目选择 ./mvnw verify 或 ./gradlew check，并确认其中确实覆盖所需模块和集成测试；不要求同时使用两套构建系统。
- 业务规则用独立单元测试；数据库事务、序列化与依赖适配通过真实集成测试验证。只 mock 整个服务层不能证明事务或实际 SQL 正确。
- 并发变更验证中断、超时、失败传播、任务回收与下游容量；使用 latch/barrier 等可控同步替代靠 sleep 等待状态碰巧出现。

## 5. 具体案例

遇到以下问题时读取 [bad/good 完整代码及断言](cases-java.md)，结合场景合同和适用边界判断。

### 审查对照

| 可疑实现 | 期望处理 |
| --- | --- |
| DTO 的 setter 无限制传播到业务内部 | 在边界校验，核心对象维护不变量与必要的不可变性 |
| record 持有 ArrayList 后宣称线程安全 | 检查防御性复制、元素可变性和发布方式 |
| catch Exception 后返回 null 或成功空列表 | 按可处理的失败分类传播，保留原因 |
| 用继承和通用 BaseService 复用不同业务流程 | 以明确职责的小对象组合，独立保留不同业务规则 |
