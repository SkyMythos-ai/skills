# 跨语言设计案例

以下全部是伪代码，表达合同与职责，不作为可直接编译的程序。适用于任意语言；落地时选用该语言的类型、错误和资源机制。对应[通用准则](core.md)第 2–9 节。

索引：C1 职责与主流程；C2 状态与故障；C3 重试与幂等；C4 行为测试；C5 抽象取舍；C6 关键注释。

<a id="c1"></a>

## C1：拆出业务动作，而不是把大方法切成编号小方法

**场景与合同**：创建订单时校验输入，由定价模块生成报价，由订单模块原子保存订单及待发布事件；通知失败不撤销已提交订单。

**Bad**

```text
handle(request):
    data = step1(request)       // 读者不知道是否校验、定价或已经写库
    data = step2(data, true)    // true 的语义不清楚
    step3(data)                // 写订单
    sendNotification(data)     // 抛错导致入口返回“创建失败”
    return data
```

**问题**：方法虽小，职责仍不可见；数据库提交后的通知错误被当作创建失败，客户端重试可能重复创建订单。

**Good**

```text
createOrder(command):
    validated = validateOrder(command)
    quote = pricing.quote(validated.items)
    order = orders.createWithEvent(validated, quote, command.idempotencyKey)
    return order

orders.createWithEvent(command, quote, key):
    // 一个本地事务内建立去重记录、订单及待发布事件。
    return transaction:
        existing = lookupByIdempotencyKey(key)
        if existing: return requireSameCommand(existing, command)
        order = insertOrder(command, quote)
        appendPendingEvent(OrderCreated(order.id))
        return order

notificationWorker:
    deliverPendingEventsWithRetryAndDeduplication()
```

**改善**：主流程表达可理解的动作；提交点在一个模块内，通知由持久事件驱动恢复。`createWithEvent` 内部还需数据库唯一约束处理同 key 并发，不能只靠先查询。

**边界**：这里业务明确要求通知最终可达才引入待发布事件。一次性脚本或允许丢弃的提示消息可直接调用并明确报告通知失败，无需 outbox。报价有效期和资金规则另按业务合同实现。

**验证**：订单提交后投递失败，重试不多建订单；相同 key 不同内容返回冲突；两个并发请求只创建一次；事件重放不重复产生业务影响。

<a id="c2"></a>

## C2：失败策略属于具体状态，不能全部套一个 fallback

**场景与合同**：资源无专属绑定时使用默认配置；有绑定但失效时必须暴露错误。缓存读取失败是否使用旧值，由该配置的安全语义决定。

**Bad**

```text
resolve(binding):
    credential = tryLoad(binding.id)  // 未绑定、不存在、禁用、超时都变成 null
    return credential or defaultCredential
```

**问题**：一条兜底把“未配置”和“配置已失效”混为一谈；显式禁用可能意外得到默认能力。

**Good**

```text
resolve(binding):
    match binding:
        Unbound:
            return loadDefault()
        Bound(id):
            match loadCredential(id):
                Active(value): return value
                Disabled: return Error(CredentialDisabled)
                Missing: return Error(BindingTargetMissing)
                Unavailable(cause):
                    return resolveDependencyFailure(id, cause, credentialPolicy)

resolveDependencyFailure(id, cause, policy):
    snapshot = lastSuccessful(id)
    if policy.permitsStale(snapshot): return snapshot.withFreshnessMetadata()
    return Error(DependencyUnavailable(cause))
```

**改善**：未配置、失效与依赖故障各有路径；是否允许旧值写成显式策略，保留版本、新鲜度和禁用水位等必要信息。

**边界**：此例不强制所有故障拒绝，也不承诺所有缓存离线可用；产品若明确允许失效后的默认回退，须作为不同的可见合同实现。权限、余额、推荐列表等数据不共享一条故障策略。

**验证**：覆盖未绑定、绑定不存在、已知禁用、依赖超时、可用旧值与已过允许期限；证明禁用不会被更旧缓存复活。

<a id="c3"></a>

## C3：重试应保护同一意图，而不是重新制造副作用

**场景与合同**：支付接口超时后结果未知，重试必须保持同一个业务意图；同一幂等键不能用于不同金额。

**Bad**

```text
for attempt in range(3):
    try:
        return charge(newUUID(), amount)
    catch Timeout:
        continue
```

**问题**：每次更换 key，相同意图会被视作多笔支付；超时不代表未扣款。

**Good**

```text
key = persistedPaymentIntent.id
payload = canonicalPaymentRequest(intent)
deadline = operationDeadline()

while retryBudgetAllows(deadline):
    result = provider.charge(key, payload, remainingTime(deadline))
    match result:
        Confirmed(receipt): return persistConfirmation(receipt)
        Rejected(reason): return BusinessRejection(reason)
        Indeterminate:
            status = provider.lookupByKey(key)
            if status.confirmed: return persistConfirmation(status.receipt)
            if status.rejected: return BusinessRejection(status.reason)
            waitWithBackoffWithin(deadline)
return PendingReconciliation(key)
```

**改善**：持久化的 key 在重启与重试中稳定，业务拒绝不重试，结果未知进入可恢复状态，总预算可控。

**边界**：前提是上游明确支持幂等键及其有效期、查询语义。同 key 不同内容必须拒绝；上游不支持时不能凭本地 UUID 宣称 exactly-once，需要单独的对账与人工处理合同。只读查询无需照搬整套支付状态机。

**验证**：模拟“上游成功但回复丢失”、进程重启、并发重试和幂等键冲突，统计实际业务副作用次数；仅数 HTTP 调用次数不足以验证。

<a id="c4"></a>

## C4：测试验证外部合同，不能复制生产条件自证

**场景与合同**：并发容量为 2，前两个在途请求占位，第三个拒绝；任一个完成后下一请求可以进入。

**Bad**

```text
expected = current < limit && enabled
actual = admissionPredicate(current, limit, enabled)
assert expected == actual
```

**问题**：测试复制了同一布尔式，无法发现占位、释放、并发竞争或状态更新丢失。

**Good**

```text
service = startWithConcurrencyLimit(2)
first = requestUntilBarrier(service, "hold-open")
second = requestUntilBarrier(service, "hold-open")
await bothReachedBarrier(first, second)

assert request(service).status == CapacityRejected
releaseBarrier(first)
await first.completedAndReleased
assert request(service).status == Accepted

releaseBarrier(second)
await service.noInflightRequests()
```

**改善**：使用受控时序验证实际请求结果与释放行为，不读取内部计数器才能判断对错。

**边界**：纯函数本身仍可用表驱动测试；不是所有测试都需要服务级 E2E。本例也不证明多实例限流、进程崩溃恢复或所有调度序列，这些需求分别补相应证据。

**验证**：测试稳定复现满额拒绝和释放后允许；每条超时都有诊断信息；finally 中释放 barrier 并关闭服务，避免失败用例泄漏任务。

<a id="c5"></a>

## C5：共享稳定语义，不把不同业务塞进万能抽象

**场景与合同**：订单列表和审计列表都查询分页，但授权、保留时间与脱敏规则不同。只有游标解码确实一致。

**Bad**

```text
list(type, filter, adminMode, includeDeleted, redact, retentionOverride):
    if type == "orders": ...
    if type == "audit": ...
    if adminMode && not redact: ...
```

**问题**：几个调用者被迫理解彼此的开关；修改一个权限分支可能影响另一个业务，通用方法只是隐藏的分支集合。

**Good**

```text
listOrders(actor, query):
    scope = orderAccess.requireReadableScope(actor)
    cursor = decodeCursor(query.cursor)
    return orders.find(scope, query.filter, cursor)

listAuditEntries(actor, query):
    scope = auditAccess.requireReadableScope(actor)
    cursor = decodeCursor(query.cursor)
    entries = audit.findWithinRetention(scope, cursor)
    return redactAuditEntries(entries, actor)
```

**改善**：复用的是含义稳定的 `decodeCursor`；授权和业务策略保持独立，读者无需追踪类型标志。

**边界**：如果多个模块确实遵循同一分页/授权协议，策略对象或参数化实现可能合理。两个相似函数不自动等于重复缺陷；十个短转发层也不自动等于好设计。

**验证**：分别验证两个业务的授权和过滤，游标测试放在公共解码边界；改变审计保留策略不应要求修改订单测试。

<a id="c6"></a>

## C6：注释解释不能丢失的合同，而不是翻译赋值

**场景与合同**：已撤销对象可能晚于撤销消息收到一份旧的有效快照，旧快照不能恢复权限。

**Bad**

```text
// 设置状态。
state = incoming.state
// 保存版本。
version = incoming.version
```

**问题**：注释复述语法，代码没有说明乱序规则；读者不知道这一赋值是否允许恢复权限。

**Good**

```text
// applySnapshot 应用同一权威版本序列中、已经验证来源与授权的快照。
// 原因：消息可能乱序；单调水位阻止旧有效值恢复权限。
// 将判断和写入放在同一原子边界，避免校验后被撤销消息穿插。
// 输入：incoming.version/state，以及当前版本、状态与撤销水位。
// 输出：Applied 并更新状态/版本，或 IgnoredStale 且原状态/版本不变。
// input → output：
//   current=7, revoked=5, incoming=(8, Active) → Applied，current=8, state=Active
//   current=7, revoked=5, incoming.version=7 → IgnoredStale，原状态保持
//   current=9, revoked=9, state=Disabled, incoming=(8, Active)
//     → IgnoredStale，仍为 Disabled，current=9
// 副作用：仅更新本地快照；不代表远端持久化或其他实例已同步。
applySnapshot(incoming):
    // 撤销版本是单调水位；晚到的旧“有效”快照不能恢复已撤销权限。
    // 水位和快照在同一原子边界内比较并更新，避免并发检查后写入竞态。
    atomicUpdate:
        if incoming.version <= revokedVersion: return IgnoredStale
        if incoming.version <= currentVersion: return IgnoredStale
        state = incoming.state
        currentVersion = incoming.version
        return Applied
```

**改善**：代码和注释共同表达设计原因、不变量与同步责任；具体 input → output 还说明哪些输入更新状态、哪些保持原状，以及本地更新不承诺远端持久化。完整注释要求见[注释规范](comments.md)。

**边界**：此例假定版本由同一权威顺序产生；来自不同域的版本不能随意比较，跨域一致性需要另行建模。简单字段赋值没有这样的合同就不必添加长注释。

**验证**：新有效值后旧值、撤销后旧有效值、相同版本重放以及并发撤销/刷新；确认新版本合法重新授权的规则也有明确合同。
