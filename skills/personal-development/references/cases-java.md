# Java 具体案例

本页给出四个可单独复制为 `Example.java` 并以 Java 17 编译的对照案例。先阅读[通用准则](core.md)和[Java 附录](java.md)；语言行为以 [record 指南](https://dev.java/learn/records/)、[异常处理指南](https://dev.java/learn/exceptions/catching-handling/) 与 [InterruptedException 合同](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/lang/InterruptedException.html) 为准。

索引：

1. J1：订单主流程以组合和小方法表达，避免万能 `BaseService`。
2. J2：`record` 对可变组件做防御性复制，明确其仍为浅不可变。
3. J3：转换异常时保留原因，依赖失败不伪装成空查询结果。
4. J4：中断是取消信号；等待资源时恢复中断状态并终止当前操作。

<a id="j1"></a>

## J1：组合与小方法

**场景与合同。** 内存运费报价必须依次校验请求、查询地区费率、计算报价；输入无效和未支持地区是不同业务拒绝。编排类拥有流程，费率目录封装自身状态。本例不表达跨系统的库存或支付原子性，相关副作用见跨语言 C1/C3。

**Bad**

<!-- example: java-j1-bad -->
```java
public class Example {
    static class BaseService {
        String quote(String region, int grams) {
            if (region == null || grams <= 0) return "E1";
            int rate = region.equals("CN") ? 8 : region.equals("JP") ? 12 : -1;
            if (rate < 0) return "E2";
            int amount = rate + (grams / 1000) * 3; // 校验、目录、计价都挤在万能服务
            return "amount=" + amount;
        }
    }

    public static void main(String[] args) {
        BaseService service = new BaseService();
        System.out.println(service.quote("CN", 1200));
    }
}
```

**坏在哪。** `BaseService` 是没有边界的杂物箱，地区费率、输入校验和计价规则都会继续堆入其中；字符串和魔法错误码要求调用方猜测业务状态。

**Good**

<!-- example: java-j1-good -->
```java
import java.util.Map;

public class Example {
    record QuoteRequest(String region, int grams) {}
    record Quote(String region, int amountCents) {}
    static final class UnsupportedRegionException extends RuntimeException {
        UnsupportedRegionException(String region) { super("未支持地区: " + region); }
    }
    static final class RateCatalog {
        private final Map<String, Integer> baseCentsByRegion = Map.of("CN", 800, "JP", 1200);
        int baseCentsFor(String region) {
            Integer rate = baseCentsByRegion.get(region);
            if (rate == null) throw new UnsupportedRegionException(region);
            return rate;
        }
    }
    static final class ShippingQuoteService {
        private final RateCatalog catalog;
        ShippingQuoteService(RateCatalog catalog) { this.catalog = catalog; }
        Quote quote(String region, int grams) {
            QuoteRequest request = validate(region, grams);
            int baseCents = catalog.baseCentsFor(request.region());
            return calculate(request, baseCents);
        }
        private QuoteRequest validate(String region, int grams) {
            if (region == null || region.isBlank() || grams <= 0) throw new IllegalArgumentException("报价请求无效");
            return new QuoteRequest(region, grams);
        }
        private Quote calculate(QuoteRequest request, int baseCents) {
            int extraKilograms = request.grams() / 1000;
            return new Quote(request.region(), baseCents + extraKilograms * 300);
        }
    }
    public static void main(String[] args) {
        ShippingQuoteService service = new ShippingQuoteService(new RateCatalog());
        if (!new Quote("CN", 1100).equals(service.quote("CN", 1200))) throw new AssertionError();
        try { service.quote("", 1); throw new AssertionError(); } catch (IllegalArgumentException expected) {}
        try { service.quote("US", 1); throw new AssertionError(); } catch (UnsupportedRegionException expected) {}
    }
}
```

**改善点。** 主流程只保留三个可读动作；费率状态封装在目录中，输入错误与未支持地区以不同类型表达。

**适用边界/何时不照搬。** 三步以内且没有独立状态的脚本可直接用具名私有方法，不必创建多个类；跨系统库存、支付和提交失败需要事务或补偿合同，本例不适用。

**验证关注点。** 覆盖有效报价、无效输入、未支持地区和费率计算边界；引入外部目录后再验证其超时、失败和一致性合同。

<a id="j2"></a>

## J2：record 的防御性复制

**场景与合同。** 配置对象接收调用方提供的标签列表，构造后列表结构不得被外部修改；调用方也不能通过访问器改变内部结构。元素本身是否可变须另行定义。

**Bad**

<!-- example: java-j2-bad -->
```java
import java.util.ArrayList;
import java.util.List;

public class Example {
    record Route(String name, List<String> tags) {}

    public static void main(String[] args) {
        List<String> supplied = new ArrayList<>();
        supplied.add("stable");
        Route route = new Route("primary", supplied);
        supplied.add("bypass-review"); // 外部仍能改变 record 的可观察状态
        route.tags().clear();            // 访问器也暴露同一个可变列表
        System.out.println(route);
    }
}
```

**坏在哪。** `record` 只保证组件引用不可重新赋值，不会深拷贝列表；原列表和访问器返回值都能改变对象状态。

**Good**

<!-- example: java-j2-good -->
```java
import java.util.ArrayList;
import java.util.List;

public class Example {
    record Route(String name, List<String> tags) {
        /**
         * Route 保存名称与不可修改的标签快照。
         * 原因：record 仅固定字段引用；复制列表才能隔离调用方后续增删。
         * input → output：("primary", ["stable"]) → 保留 stable 的快照；
         * 原列表随后添加标签不影响快照；修改访问器返回列表会失败。
         * @param name 非 null、非空白的名称，原样保存
         * @param tags 非 null 且不含 null 元素的列表，允许空列表；String 元素不可变
         * @throws IllegalArgumentException name 为 null 或空白
         * @throws NullPointerException tags 或其中元素为 null
         */
        Route {
            if (name == null || name.isBlank()) throw new IllegalArgumentException("名称为空");
            // 复制容器并拒绝结构修改；String 元素本身不可变。
            tags = List.copyOf(tags);
        }
    }

    public static void main(String[] args) {
        List<String> supplied = new ArrayList<>();
        supplied.add("stable");
        Route route = new Route("primary", supplied);
        supplied.add("bypass-review");
        if (!route.tags().equals(List.of("stable"))) throw new AssertionError();
        try { route.tags().add("other"); throw new AssertionError(); }
        catch (UnsupportedOperationException expected) {}
        try { new Route(" ", List.of()); throw new AssertionError(); }
        catch (IllegalArgumentException expected) {}
    }
}
```

**改善点。** 紧凑构造器在边界验证并复制列表，调用方无法更改容器结构；不变量靠类型自身维护。

**适用边界/何时不照搬。** 含 `byte[]`、`Date` 或可变元素时，需要对每个可变值复制，访问器也返回副本；大对象或刻意共享的只读视图应明示所有权和并发合同，不能盲目复制。

**验证关注点。** 构造后修改原列表、修改访问器返回值、空元素/空列表和元素可变性都应按实际合同测试。

<a id="j3"></a>

## J3：异常原因与空结果

**场景与合同。** 查询用户目录时，有团队与没有团队都是有效结果；目录 `IOException` 是依赖故障，调用方必须能区分并记录根因。程序缺陷仍按原类型传播。

**Bad**

<!-- example: java-j3-bad -->
```java
import java.io.IOException;
import java.util.List;

public class Example {
    interface Directory { List<String> findTeams(String userId) throws IOException; }
    static List<String> teamsFor(Directory directory, String userId) {
        try {
            return directory.findTeams(userId);
        } catch (Exception ignored) {
            return List.of(); // 网络故障与“没有团队”被混为一谈
        }
    }
    public static void main(String[] args) {
        Directory unavailable = id -> { throw new IOException("connection refused"); };
        System.out.println(teamsFor(unavailable, "u-1"));
    }
}
```

**坏在哪。** 捕获所有异常后返回空列表抹掉依赖故障，授权或展示层会据此作出错误业务决策；同样会错误吞没程序缺陷。

**Good**

<!-- example: java-j3-good -->
```java
import java.io.IOException;
import java.util.List;

public class Example {
    interface Directory { List<String> findTeams(String userId) throws IOException; }
    static final class DirectoryUnavailableException extends RuntimeException {
        DirectoryUnavailableException(String userId, IOException cause) {
            super("无法查询用户目录: " + userId, cause);
        }
    }
    static List<String> teamsFor(Directory directory, String userId) {
        if (userId == null || userId.isBlank()) throw new IllegalArgumentException("用户标识为空");
        try {
            return directory.findTeams(userId); // 正常空列表仍是业务结果
        } catch (IOException cause) {
            throw new DirectoryUnavailableException(userId, cause);
        }
    }
    public static void main(String[] args) {
        Directory populated = id -> List.of("engineering");
        if (!teamsFor(populated, "u-1").equals(List.of("engineering"))) throw new AssertionError();
        Directory empty = id -> List.of();
        if (!teamsFor(empty, "u-1").isEmpty()) throw new AssertionError();
        Directory unavailable = id -> { throw new IOException("connection refused"); };
        try {
            teamsFor(unavailable, "u-1"); throw new AssertionError();
        } catch (DirectoryUnavailableException expected) {
            if (expected.getCause() == null || !"connection refused".equals(expected.getCause().getMessage())) throw new AssertionError();
        }
        Directory defective = id -> { throw new NullPointerException("bug"); };
        try { teamsFor(defective, "u-1"); throw new AssertionError(); }
        catch (NullPointerException expected) { if (!"bug".equals(expected.getMessage())) throw new AssertionError(); }
    }
}
```

**改善点。** 有团队和空结果都保持为有效结果；仅已声明的依赖 I/O 故障转换为调用方可处理的类型，保留 `cause` 与用户上下文，程序缺陷不被包装。

**适用边界/何时不照搬。** 如果调用方能从某个已知异常恢复，应定义更精确的异常类型或结果对象；不应把程序缺陷（如 `NullPointerException`）一律包装为依赖不可用。

**验证关注点。** 分别验证非空结果、空结果、无效输入、I/O 失败类型与原因链，以及 `NullPointerException` 原样传播和上层实际采取的失败动作。

<a id="j4"></a>

## J4：中断生命周期

**场景与合同。** 工作线程等待队列任务；中断表示所有者要求停止。方法不继续等待或伪造成功，并在无法声明 checked 异常的边界恢复中断标志，供上层生命周期管理器观察。

**Bad**

<!-- example: java-j4-bad -->
```java
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

public class Example {
    static String next(BlockingQueue<String> queue) {
        try {
            return queue.take();
        } catch (InterruptedException ignored) {
            return ""; // 吞掉取消并把失败伪装成一条任务
        }
    }
    public static void main(String[] args) {
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(1);
        Thread.currentThread().interrupt();
        System.out.println(next(queue));
    }
}
```

**坏在哪。** `take` 清除中断标志后，代码既不恢复也不终止；调用方得到空字符串，无法区分真正任务与取消。

**Good**

<!-- example: java-j4-good -->
```java
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;

public class Example {
    static final class WorkCancelledException extends RuntimeException {
        WorkCancelledException(InterruptedException cause) { super("等待任务时被取消", cause); }
    }
    static String next(BlockingQueue<String> queue) {
        try {
            return queue.take();
        } catch (InterruptedException cause) {
            // 本层不能传播 checked 异常，恢复信号并明确终止本次工作。
            Thread.currentThread().interrupt();
            throw new WorkCancelledException(cause);
        }
    }
    public static void main(String[] args) {
        BlockingQueue<String> queue = new ArrayBlockingQueue<>(1);
        queue.add("job-1");
        if (!"job-1".equals(next(queue))) throw new AssertionError();
        Thread.currentThread().interrupt();
        try { next(queue); throw new AssertionError(); }
        catch (WorkCancelledException expected) {
            if (expected.getCause() == null || !Thread.currentThread().isInterrupted()) throw new AssertionError();
        } finally {
            Thread.interrupted(); // 清理演示线程，避免影响后续执行环境
        }
    }
}
```

**改善点。** 取消有独立错误类型和原因链，中断状态得到恢复，调用方可停止循环、释放资源或等待线程退出。

**适用边界/何时不照搬。** 若公开 API 已声明 `InterruptedException`，优先直接传播；只有某一层的合同明确“消费中断”时才不恢复，并且要完成对应的终止与清理动作。

**验证关注点。** 验证有任务时正常返回、线程已中断时立即失败、原因链存在且中断标志可被外层观察；涉及执行器时还应验证取消、关闭和线程回收。
