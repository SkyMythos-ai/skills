# Go 对照案例

这些案例与 [core.md](core.md)、[go.md](go.md) 一起使用。每段代码都只依赖标准库且可独立编译；`bad` 段只用于阅读和编译，`good` 段的 `main` 用断言覆盖成功及相邻边界或失败。不要把案例中的内存实现当作生产存储方案。

| 案例 | 主题 | 规则与依据 |
| --- | --- | --- |
| [G1](#g1) | 消费方小接口与流程 | [Go Code Review Comments: Interfaces](https://go.dev/wiki/CodeReviewComments#interfaces) |
| [G2](#g2) | 错误与有效空值 | [Handle Errors](https://go.dev/wiki/CodeReviewComments#handle-errors) |
| [G3](#g3) | 取消和 goroutine 生命周期 | [Contexts](https://go.dev/wiki/CodeReviewComments#contexts)、[Goroutine Lifetimes](https://go.dev/wiki/CodeReviewComments#goroutine-lifetimes) |
| [G4](#g4) | 资源关闭与结果不确定 | [Effective Go: Defer](https://go.dev/doc/effective_go#defer) |

<a id="g1"></a>

## G1：消费者定义小接口并组合流程

**场景与合同。** 报表流程只需要按 ID 读取账户余额，再校验业务条件并格式化结果。它不应依赖存储的创建、删除和迁移能力；缺失账户必须返回错误。

**Bad**

<!-- example: go-g1-bad -->
```go
package main

import (
	"errors"
	"fmt"
)

var ErrNegativeBalance = errors.New("negative balance")

// 存储方为自身全部能力预先定义大接口。
type AccountStore interface {
	Find(string) (int, bool)
	Save(string, int)
	Delete(string)
	Migrate() error
}

type memoryStore map[string]int

func (m memoryStore) Find(id string) (int, bool) { v, ok := m[id]; return v, ok }
func (m memoryStore) Save(id string, v int)      { m[id] = v }
func (m memoryStore) Delete(id string)           { delete(m, id) }
func (m memoryStore) Migrate() error             { return nil }

// 报表被迫依赖四项能力，测试替身也必须实现它们。
func report(store AccountStore, id string) (string, error) {
	balance, ok := store.Find(id)
	if !ok {
		return "", fmt.Errorf("account %q not found", id)
	}
	if balance < 0 {
		return "", ErrNegativeBalance
	}
	return fmt.Sprintf("%s=%d", id, balance), nil
}

func main() {
	_, _ = report(memoryStore{"a": 10, "debt": -1}, "a")
}
```

**为何坏。** `report` 的变化原因只是“如何读取余额”，却被存储方的全部操作绑定；大接口掩盖了真正的消费契约。

**Good**

<!-- example: go-g1-good -->
```go
package main

import (
	"errors"
	"fmt"
)

var ErrAccountMissing = errors.New("account missing")

// 消费方只声明流程实际需要的能力。
type balanceFinder interface{ Balance(string) (int, error) }
type memoryLedger map[string]int

func (m memoryLedger) Balance(id string) (int, error) {
	v, ok := m[id]
	if !ok {
		return 0, fmt.Errorf("%w: %s", ErrAccountMissing, id)
	}
	return v, nil
}

func validateBalance(v int) error {
	if v < 0 {
		return errors.New("negative balance")
	}
	return nil
}
func renderReport(id string, balance int) string { return fmt.Sprintf("%s=%d", id, balance) }
func report(f balanceFinder, id string) (string, error) {
	v, err := f.Balance(id)
	if err != nil {
		return "", err
	}
	if err := validateBalance(v); err != nil {
		return "", err
	}
	return renderReport(id, v), nil
}

func main() {
	ledger := memoryLedger{"a": 10, "debt": -1}
	got, err := report(ledger, "a")
	if err != nil || got != "a=10" {
		panic("successful report contract broken")
	}
	_, err = report(ledger, "missing")
	if !errors.Is(err, ErrAccountMissing) {
		panic("missing account was not preserved")
	}
	_, err = report(ledger, "debt")
	if err == nil {
		panic("invalid balance was accepted")
	}
}
```

**改善点。** 主流程直接消费窄接口，再校验、渲染；读取本身没有独立规则，保留为转发层只会增加跳转。测试或替换实现仅需满足 `balanceFinder`。

**适用边界。** 提取接口的前提是存在消费方隔离、替换或测试需求；只有一个直连调用且具体类型已是清晰合同，不必为此新增接口。

**验证关注点。** 对真实实现和替身都验证正常余额、缺失与非法余额；接口增加方法时应检查是否仍是消费方所需能力。

<a id="g2"></a>

## G2：查询失败不能伪装为有效空结果

**场景与合同。** 目录允许存在“有效但没有条目”的团队；依赖故障与团队不存在必须让调用者区分，不能都变成空切片。

**Bad**

<!-- example: go-g2-bad -->
```go
package main

import "errors"

type directory struct {
	failed  bool
	members map[string][]string
}

func (d directory) read(team string) ([]string, error) {
	if d.failed {
		return nil, errors.New("directory unavailable")
	}
	return d.members[team], nil
}

// 把依赖故障伪装为空团队，调用方会误发“无成员”业务动作。
func members(d directory, team string) []string {
	items, err := d.read(team)
	if err != nil {
		return []string{}
	}
	return items
}

func main() {
	d := directory{failed: true}
	_ = members(d, "ops")
}
```

**为何坏。** 空集合是合法业务结果，吞掉错误使调用方无法选择重试、拒绝或展示降级状态。

**Good**

<!-- example: go-g2-good -->
```go
package main

import (
	"errors"
	"fmt"
)

var ErrTeamMissing = errors.New("team missing")
var ErrDirectoryUnavailable = errors.New("directory unavailable")

type directory struct {
	failed  bool
	members map[string][]string
}

// read 读取团队成员，并区分有效空团队、缺失团队和目录故障。
// 原因：空集合是合法业务结果，故障不能伪装为空；返回副本避免外部修改内部名单。
// 输入：team 为精确匹配的团队标识；d.failed 表示依赖不可用。
// 输出：成功返回成员快照和 nil；失败返回 nil 和可用 errors.Is 判断的原因。
// input → output：已有空团队 ops → len(items)=0, err=nil；
// 不存在的团队 → ErrTeamMissing；d.failed=true → ErrDirectoryUnavailable。
// 副作用：不修改目录；空快照可以为 nil，不承诺 JSON 编码为 []。
func (d directory) read(team string) ([]string, error) {
	if d.failed {
		return nil, ErrDirectoryUnavailable
	}
	items, ok := d.members[team]
	if !ok {
		return nil, fmt.Errorf("%w: %s", ErrTeamMissing, team)
	}
	return append([]string(nil), items...), nil
}

func members(d directory, team string) ([]string, error) {
	return d.read(team)
}

func main() {
	empty := directory{members: map[string][]string{"ops": {}}}
	items, err := members(empty, "ops")
	if err != nil || len(items) != 0 {
		panic("valid empty team changed meaning")
	}
	_, err = members(empty, "missing")
	if !errors.Is(err, ErrTeamMissing) {
		panic("missing team was hidden")
	}
	_, err = members(directory{failed: true}, "ops")
	if !errors.Is(err, ErrDirectoryUnavailable) {
		panic("dependency failure was hidden")
	}
}
```

**改善点。** 空、缺失和依赖不可用成为可检查的三种结果；错误原因可由上层决定重试或映射协议状态。

**适用边界。** 若产品合同明确规定“不可用时使用带新鲜度的最后成功快照”，可返回该快照和单独的降级状态；不能仅返回空集合。

**验证关注点。** 覆盖有效空值、缺失、依赖失败及返回集合不会被调用方修改后污染内部状态。

<a id="g3"></a>

## G3：goroutine 必须有取消与退出归属

**场景与合同。** 请求启动一个后台计算任务；已取消的输入直接被拒绝，工作阶段取消必须退出，创建者必须等待其退出。任务在通过最后一次取消检查后完成，即使随后收到取消也可返回完成值；这是协作取消的竞态边界。

**Bad**

<!-- example: go-g3-bad -->
```go
package main

type result struct{ value int }

func start(input int) <-chan result {
	out := make(chan result)
	go func() {
		// 接收者提前返回时，这次发送会永久阻塞。
		out <- result{value: input * 2}
	}()
	return out
}

func main() {
	_ = start(21)
	// main 退出不证明 goroutine 有可控的退出合同。
}
```

**为何坏。** 任务没有取消路径，发送依赖一个可能已离开的接收者；该泄漏在短命令中很容易被掩盖。

**Good**

<!-- example: go-g3-good -->
```go
package main

import (
	"context"
	"errors"
)

var ErrCanceled = errors.New("calculation canceled")

type result struct {
	value int
	err   error
}

func start(ctx context.Context, input int, gate <-chan struct{}) (<-chan result, <-chan struct{}) {
	out := make(chan result, 1)
	done := make(chan struct{})
	// 预取消输入必须确定地拒绝，不进入 select 竞态。
	if ctx.Err() != nil {
		out <- result{err: ErrCanceled}
		close(done)
		return out, done
	}
	go func() {
		defer close(done)
		select {
		case <-ctx.Done():
			out <- result{err: ErrCanceled}
			return
		case <-gate:
		}
		// gate 与取消同时就绪时，最后检查让已观察到的取消优先。
		if ctx.Err() != nil {
			out <- result{err: ErrCanceled}
			return
		}
		out <- result{value: input * 2}
	}()
	return out, done
}

func main() {
	ready := make(chan struct{})
	close(ready)
	ctx, cancel := context.WithCancel(context.Background())
	out, done := start(ctx, 21, ready)
	got := <-out
	if got.err != nil || got.value != 42 {
		panic("successful task contract broken")
	}
	<-done
	canceled, cancelNow := context.WithCancel(context.Background())
	cancelNow()
	out, done = start(canceled, 21, ready)
	got = <-out
	if !errors.Is(got.err, ErrCanceled) {
		panic("cancellation was not reported")
	}
	<-done
	inProgress, stop := context.WithCancel(context.Background())
	blocked := make(chan struct{})
	out, done = start(inProgress, 21, blocked)
	stop()
	got = <-out
	if !errors.Is(got.err, ErrCanceled) {
		panic("in-progress cancellation was not reported")
	}
	<-done
	cancel()
}
```

**改善点。** `Context` 沿调用边界进入任务；预检查消除“已取消输入”随机性，受控 gate 无需 `sleep` 即可验证工作中取消，`done` 证明创建者已回收任务。

**适用边界。** 真正应脱离请求的工作必须交给有独立监督、重试和关闭语义的后台系统；不能把 `context.Background()` 当作默认逃逸手段。

**验证关注点。** 验证正常、预取消、工作中取消和等待回收；再按实际 I/O 的可取消点验证不会在取消后继续占用锁或配额。

<a id="g4"></a>

## G4：关闭失败表达为未确认而不是成功

**场景与合同。** 写入器的 `Close` 代表把已缓存的数据提交出去；无论写入是否失败都必须恰好关闭一次。写入或关闭失败的原因都要可检查，关闭失败还表示结果未确认。

**Bad**

<!-- example: go-g4-bad -->
```go
package main

import "errors"

type writer struct {
	writeFails, closeFails bool
	wrote, closeCalls      int
}

func (w *writer) Write() error {
	if w.writeFails {
		return errors.New("write failed")
	}
	w.wrote++
	return nil
}
func (w *writer) Close() error {
	w.closeCalls++
	if w.closeFails {
		return errors.New("flush failed")
	}
	return nil
}

// defer 中的关闭错误被忽略，调用者获得错误的成功结论。
func publish(w *writer) error {
	defer w.Close()
	return w.Write()
}

func main() {
	_ = publish(&writer{writeFails: true, closeFails: true})
}
```

**为何坏。** `defer` 能保证调用释放，但不能自动把关闭失败并入返回合同；外部系统可能已部分接受操作。

**Good**

<!-- example: go-g4-good -->
```go
package main

import (
	"errors"
)

var ErrOutcomeUnknown = errors.New("publish outcome unknown")
var ErrWrite = errors.New("write failed")
var ErrClose = errors.New("flush failed")

type writer struct {
	writeFails, closeFails bool
	wrote, closeCalls      int
}

func (w *writer) Write() error {
	if w.writeFails {
		return ErrWrite
	}
	w.wrote++
	return nil
}
func (w *writer) Close() error {
	w.closeCalls++
	if w.closeFails {
		return ErrClose
	}
	return nil
}

func publish(w *writer) error {
	writeErr := w.Write()
	closeErr := w.Close()
	if closeErr != nil {
		return errors.Join(writeErr, ErrOutcomeUnknown, closeErr)
	}
	return writeErr
}

func main() {
	ok := &writer{}
	if err := publish(ok); err != nil || ok.wrote != 1 || ok.closeCalls != 1 {
		panic("successful publish contract broken")
	}
	writeFailed := &writer{writeFails: true}
	err := publish(writeFailed)
	if !errors.Is(err, ErrWrite) || writeFailed.closeCalls != 1 {
		panic("write failure skipped close or lost cause")
	}
	uncertain := &writer{closeFails: true}
	err = publish(uncertain)
	if uncertain.wrote != 1 || uncertain.closeCalls != 1 || !errors.Is(err, ErrClose) || !errors.Is(err, ErrOutcomeUnknown) {
		panic("close failure was not preserved as unknown")
	}
	bothFailed := &writer{writeFails: true, closeFails: true}
	err = publish(bothFailed)
	if bothFailed.closeCalls != 1 || !errors.Is(err, ErrWrite) || !errors.Is(err, ErrClose) || !errors.Is(err, ErrOutcomeUnknown) {
		panic("combined failure lost a cause or closed incorrectly")
	}
}
```

**改善点。** 所有路径先写后关，关闭恰好一次；`errors.Join` 同时保留写入、关闭和未确认原因，调用方可查询、去重或补偿。此示例需要 Go 1.20+。

**适用边界。** 只读资源的关闭失败未必改变业务结果，可按合同记录或返回；关键提交、写入和事务终结不能照搬“忽略关闭错误”。

**验证关注点。** 覆盖成功、写入失败、关闭失败和二者同时失败，并断言每个路径恰好关闭一次及各原因仍可由 `errors.Is` 识别。
