# Rust 对照案例

这些案例与 [core.md](core.md)、[rust.md](rust.md) 一起使用。每段代码仅使用标准库且可独立编译；`bad` 段只用于阅读和编译，`good` 段的 `main` 通过断言覆盖成功和相邻失败/边界。示例不替代项目的异步运行时、持久化或错误框架合同。

| 案例 | 主题 | 规则与依据 |
| --- | --- | --- |
| [R1](#r1) | enum 状态与转移 | [Rust API Guidelines: Type safety](https://rust-lang.github.io/api-guidelines/type-safety.html) |
| [R2](#r2) | `Result` 与 `unwrap` | [The Rust Book: Error Handling](https://doc.rust-lang.org/book/ch09-00-error-handling.html) |
| [R3](#r3) | 借用、所有权与共享 | [Rust API Guidelines: Caller control](https://rust-lang.github.io/api-guidelines/flexibility.html#c-caller-control) |
| [R4](#r4) | RAII 与显式失败 | [Rust API Guidelines: Destructors](https://rust-lang.github.io/api-guidelines/dependability.html#c-dtor-fail) |

<a id="r1"></a>

## R1：用 enum 排除互斥状态组合

**场景与合同。** 付款只能处于待处理、已批准或已拒绝之一；批准和拒绝都必须带各自所需事实，且终态不可再次审批。

**Bad**

<!-- example: rust-r1-bad -->
```rust
#[derive(Debug)]
struct Payment {
    approved: bool,
    rejected: bool,
    reason: Option<String>,
}

fn approve(payment: &mut Payment) {
    payment.approved = true;
}

fn reject(payment: &mut Payment, reason: String) {
    payment.rejected = true;
    payment.reason = Some(reason);
}

fn main() {
    let mut payment = Payment {
        approved: false,
        rejected: false,
        reason: None,
    };
    approve(&mut payment);
    reject(&mut payment, "risk rule".into());
    // 编译器允许“已批准且已拒绝”的非法组合。
    let _ = payment;
}
```

**为何坏。** 多个 bool 和可选字段允许相互矛盾的组合，状态转移规则散落在调用方，难以审查完整性。

**Good**

<!-- example: rust-r1-good -->
```rust
#[derive(Debug, PartialEq)]
enum Payment {
    Pending { id: u64 },
    Approved { id: u64, receipt: String },
    Rejected { id: u64, reason: String },
}

/// approve 将待处理付款转为已批准。
/// 原因：独占借用保留调用方对原状态的所有权，拒绝转换时不会丢失终态事实。
/// 输入：付款的当前状态和 receipt；本例原样保存 receipt，不校验其格式。
/// 输出：成功返回 Ok(()) 并修改状态；失败返回 Err，付款状态保持原样。
/// input → output：Pending{id:7}, "r-7" → Ok(())，状态为 Approved{id:7, receipt:"r-7"}；
/// 已批准付款, "again" → Err，原 id/receipt 均保留。
/// # Errors
/// 当前状态非 Pending 时拒绝；无外部 I/O，也不代表真实支付已完成。
fn approve(payment: &mut Payment, receipt: String) -> Result<(), &'static str> {
    match payment {
        Payment::Pending { id } => {
            let id = *id;
            *payment = Payment::Approved { id, receipt };
            Ok(())
        }
        _ => Err("only pending payment can be approved"),
    }
}

fn reject(payment: &mut Payment, reason: String) -> Result<(), &'static str> {
    match payment {
        Payment::Pending { id } => {
            let id = *id;
            *payment = Payment::Rejected { id, reason };
            Ok(())
        }
        _ => Err("only pending payment can be rejected"),
    }
}

fn main() {
    let mut approved = Payment::Pending { id: 7 };
    assert_eq!(approve(&mut approved, "r-7".into()), Ok(()));
    assert_eq!(
        approved,
        Payment::Approved {
            id: 7,
            receipt: "r-7".into()
        }
    );
    assert_eq!(
        approve(&mut approved, "again".into()),
        Err("only pending payment can be approved")
    );
    assert_eq!(
        approved,
        Payment::Approved {
            id: 7,
            receipt: "r-7".into()
        }
    );
    let mut rejected = Payment::Pending { id: 8 };
    assert_eq!(reject(&mut rejected, "risk".into()), Ok(()));
    assert_eq!(
        rejected,
        Payment::Rejected {
            id: 8,
            reason: "risk".into()
        }
    );
}
```

**改善点。** 类型排除“批准且拒绝”这类互斥组合；`match` 集中转移，借用修改使拒绝转换后原终态和其中事实仍由调用方持有。

**适用边界。** enum 不能自动保证 receipt 非空、金额范围等变体内部不变量，仍应在构造/转移边界校验。两三个无业务差异的局部标志不必强行建状态机。

**验证关注点。** 验证每个合法转移、每个终态拒绝和状态携带事实；增加变体时让编译器协助发现漏处理分支。

<a id="r2"></a>

## R2：可恢复失败返回 Result，而非 unwrap

**场景与合同。** 配额字符串来自不可信配置；格式错误是调用方可报告的输入故障，不应使进程 panic。

**Bad**

<!-- example: rust-r2-bad -->
```rust
fn quota_for(text: &str) -> u32 {
    // 配置错误会把普通业务失败升级为进程 panic。
    text.parse::<u32>().unwrap()
}

fn main() {
    let _ = quota_for("42");
}
```

**为何坏。** `unwrap` 代表“失败不可能或无需恢复”的断言；不可信边界显然不满足这个前提，调用方也失去错误语义。

**Good**

<!-- example: rust-r2-good -->
```rust
use std::error::Error;
use std::fmt;
use std::num::ParseIntError;

#[derive(Debug)]
enum QuotaError {
    Empty,
    InvalidNumber(ParseIntError),
    Zero,
}

impl fmt::Display for QuotaError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Empty => write!(f, "quota is empty"),
            Self::InvalidNumber(_) => write!(f, "quota is not an unsigned integer"),
            Self::Zero => write!(f, "quota must be positive"),
        }
    }
}
impl Error for QuotaError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::InvalidNumber(source) => Some(source),
            _ => None,
        }
    }
}

fn quota_for(text: &str) -> Result<u32, QuotaError> {
    if text.is_empty() {
        return Err(QuotaError::Empty);
    }
    let value = text.parse::<u32>().map_err(QuotaError::InvalidNumber)?;
    if value == 0 {
        return Err(QuotaError::Zero);
    }
    Ok(value)
}

fn main() {
    assert!(matches!(quota_for("42"), Ok(42)));
    assert!(matches!(quota_for(""), Err(QuotaError::Empty)));
    let invalid = quota_for("many").unwrap_err();
    assert!(matches!(invalid, QuotaError::InvalidNumber(_)));
    assert!(invalid.source().is_some());
    assert!(matches!(quota_for("0"), Err(QuotaError::Zero)));
}
```

**改善点。** 错误变体是稳定的分支依据，`InvalidNumber` 还保留原始 `ParseIntError` 作为 source；边界校验和业务约束可独立验证。

**适用边界。** 测试、原型或紧邻已证明不变量的内部断言可用 `expect`，但应说明理由；公共或请求处理路径不可用它替代错误合同。

**验证关注点。** 覆盖有效输入、空、格式错误和业务无效值；上层应基于错误变体而非格式化文本决定 HTTP/CLI 映射。

<a id="r3"></a>

## R3：先厘清所有权，再使用 clone 或共享

**场景与合同。** 会话余额的唯一所有者是调用方。记录扣款时必须修改该会话；只读展示不应为方便而复制整个会话。

**Bad**

<!-- example: rust-r3-bad -->
```rust
#[derive(Clone, Debug)]
struct Session {
    user: String,
    credits: u32,
}

fn charge(mut session: Session, amount: u32) -> bool {
    if session.credits < amount {
        return false;
    }
    session.credits -= amount;
    true
}

fn main() {
    let session = Session {
        user: "a".into(),
        credits: 10,
    };
    // clone 掩盖所有权问题，扣款落在临时副本。
    let _ = charge(session.clone(), 3);
    let _ = session;
}
```

**为何坏。** 复制使代码“能编译”，却把领域事实写进丢弃的副本；当真正需要并发共享时，盲目 clone 也不能建立同步合同。

**Good**

<!-- example: rust-r3-good -->
```rust
#[derive(Debug, PartialEq)]
struct Session {
    user: String,
    credits: u32,
}

fn display_name(session: &Session) -> &str {
    &session.user
}
fn charge(session: &mut Session, amount: u32) -> Result<(), &'static str> {
    if session.credits < amount {
        return Err("insufficient credits");
    }
    session.credits -= amount;
    Ok(())
}

fn main() {
    let mut session = Session {
        user: "a".into(),
        credits: 10,
    };
    assert_eq!(display_name(&session), "a");
    assert_eq!(charge(&mut session, 3), Ok(()));
    assert_eq!(session.credits, 7);
    assert_eq!(charge(&mut session, 8), Err("insufficient credits"));
    assert_eq!(session.credits, 7);
}
```

**改善点。** `&Session` 表达只读观察，`&mut Session` 表达唯一修改权；失败后余额保持不变也成为可验证合同。

**适用边界。** 必须跨线程或长期任务共享时，可使用 `Arc` 加合适同步原语，并明确锁、取消和所有者；不要因这个例子禁止为独立快照而有意 clone。

**验证关注点。** 验证成功修改、余额不足不修改、借用范围不跨越不必要的异步/锁边界；共享版本再验证同步和顺序语义。

<a id="r4"></a>

## R4：RAII 负责释放，显式终结负责报告失败

**场景与合同。** 批处理缓冲区离开作用域时可以由 `Drop` 做尽力清理，但“提交成功”必须由可返回 `Result` 的 `finish` 明确确认。

**Bad**

<!-- example: rust-r4-bad -->
```rust
struct Batch {
    close_fails: bool,
    committed: bool,
}

impl Drop for Batch {
    fn drop(&mut self) {
        // Drop 无法把提交失败报告给调用方。
        if self.close_fails {
            self.committed = false;
        }
    }
}

fn publish(close_fails: bool) {
    let mut batch = Batch {
        close_fails,
        committed: false,
    };
    batch.committed = true;
}

fn main() {
    publish(true);
}
```

**为何坏。** 析构的主要责任是可靠释放；把关键提交藏进 `Drop` 会让调用方无法区分成功、失败或需要补偿的未知结果。

**Good**

<!-- example: rust-r4-good -->
```rust
use std::cell::Cell;
use std::rc::Rc;

#[derive(Debug, PartialEq)]
enum FinishError {
    FlushFailed,
}

struct Resource {
    releases: Rc<Cell<u32>>,
}
impl Drop for Resource {
    fn drop(&mut self) {
        self.releases.set(self.releases.get() + 1);
    }
}

struct Batch {
    flush_fails: bool,
    wrote: bool,
    resource: Resource,
}
impl Batch {
    fn new(flush_fails: bool, releases: Rc<Cell<u32>>) -> Self {
        Self {
            flush_fails,
            wrote: false,
            resource: Resource { releases },
        }
    }
    fn write(&mut self) {
        self.wrote = true;
    }
    fn finish(self) -> Result<(), FinishError> {
        if self.flush_fails {
            return Err(FinishError::FlushFailed);
        }
        Ok(())
    }
}

fn publish(flush_fails: bool, releases: Rc<Cell<u32>>) -> Result<(), FinishError> {
    let mut batch = Batch::new(flush_fails, releases);
    batch.write();
    batch.finish()
}

fn main() {
    let success_releases = Rc::new(Cell::new(0));
    assert_eq!(publish(false, success_releases.clone()), Ok(()));
    assert_eq!(success_releases.get(), 1);
    let failed_releases = Rc::new(Cell::new(0));
    assert_eq!(
        publish(true, failed_releases.clone()),
        Err(FinishError::FlushFailed)
    );
    assert_eq!(failed_releases.get(), 1);
    let abandoned_releases = Rc::new(Cell::new(0));
    {
        let _batch = Batch::new(false, abandoned_releases.clone());
    }
    assert_eq!(abandoned_releases.get(), 1); // 放弃路径仅释放，不宣称提交。
}
```

**改善点。** 成功提交只由 `finish` 的 `Ok` 表示；外部可观察 fixture 证明成功、flush 失败和放弃三条路径都恰好释放一次，而放弃不会伪造业务确认。

**适用边界。** 纯内存或无失败关闭可以完全交给 RAII；事务、远端 flush、异步关闭和持久化确认必须有可等待、可报告失败的终结接口。

**验证关注点。** 验证 `finish` 成功、失败和放弃路径；真实实现还要验证幂等、部分提交后的查询/补偿及不在 `Drop` 中阻塞或 panic。
