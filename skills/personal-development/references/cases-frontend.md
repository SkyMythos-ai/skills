# 前端 Bad / Good 案例

配合[前端编码](frontend.md)与[企业 UI/UX](enterprise-ui.md)按问题读取。TSX 是标明上下文的教学片段，省略组件外壳与依赖；设计案例是行为对照。`verify_examples.py` 不验证这些片段，生产保证由目标项目检查与浏览器行为证明。

<a id="f1"></a>

## F1：派生数据由渲染计算

**场景与合同**：组件已收到当前环境的 `services: Service[]` 和 `query: string`，服务具有稳定 `id` 与 `name`；过滤应对应当前输入，行内编辑状态始终归属同一服务。

**Bad**（组件内片段）：

```tsx
const [visible, setVisible] = useState<Service[]>([]);
useEffect(() => {
  setVisible(services.filter((service) => service.name.includes(query)));
}, [services, query]);
return visible.map((service, index) => (
  <ServiceRow key={index} service={service} />
));
```

**问题**：为计算结果新增状态与 Effect，使当前输入先对应旧结果，再额外渲染；排序/过滤后索引 key 会把行内状态关联到别的服务。

**Good**（同一组件内片段）：

```tsx
const visible = services.filter((service) => service.name.includes(query));
return visible.map((service) => (
  <ServiceRow key={service.id} service={service} />
));
```

**改善与边界**：保留一个权威数据源和稳定资源身份；昂贵计算测量后再缓存。远端搜索、延迟输入或用户可独立编辑的副本具有不同合同，不把本例扩展为禁止所有 Effect 或独立状态。

**验证**：修改查询后结果立即对应当前输入；编辑 B 行后过滤或重排，B 的编辑状态不转移给 A。请求归属与环境切换由数据层另行验证，本例不证明网络正确。

<a id="f2"></a>

## F2：状态类名可构建且语义可读

**场景与合同**：发布状态为 `"queued" | "running" | "failed"`，页面需要显示状态文字及对应样式；Tailwind 使用项目正常源码扫描，没有为运行时组合专门声明来源。

**Bad**（组件内片段）：

```tsx
const color = status === "failed" ? "red" : "blue";
return <span className={`bg-${color}-100 text-${color}-800`}>{status}</span>;
```

**问题**：源码没有完整类名，产物可能缺失样式；排队与执行也未体现不同含义，用户文案直接暴露协议枚举。

**Good**（组件内片段；示例使用 Tailwind 常规色板，项目有状态 token 时替换为对应完整类名）：

```tsx
type PublishStatus = "queued" | "running" | "failed";
const presentation = {
  queued: { label: "排队中", className: "bg-slate-100 text-slate-800" },
  running: { label: "发布中", className: "bg-blue-100 text-blue-800" },
  failed: { label: "发布失败", className: "bg-red-100 text-red-800" },
} satisfies Record<PublishStatus, { label: string; className: string }>;

const item = presentation[status]; // status 已在数据边界校验为 PublishStatus。
return <span className={item.className}>{item.label}</span>;
```

**改善与边界**：有限状态、文案和完整类名一一对应，文字承担状态语义；`satisfies` 需目标 TypeScript 支持，旧项目采用等价类型标注，不为本例升级。多语言项目使用翻译键；配色与主题对比度另行验证。

**验证**：以项目生产构建检查三种状态的真实样式与文字；新增状态后类型检查要求补齐映射。状态文字仍可辨识，不只依赖色觉；不把类型映射当作运行时输入校验。

<a id="f3"></a>

## F3：首次创建可完成，高级能力可发现

**场景与合同**：用户创建模型服务；项目已有受支持的模型与资源默认值，高级选项包含调度、探针与重试策略。创建响应表示任务已受理，实际就绪须继续查询。

**Bad**：首屏展示全部底层字段，要求用户手填调度表达式；提交后清空表单并提示“部署成功”。新手难以选择，失败后需重填，也混淆受理与就绪。

**Good**：默认显示服务名称、模型、目标环境和资源概要；推荐值说明依据，费用/容量与权限影响在提交前可见。“高级配置”展示当前非默认项并支持展开；提交后显示“已受理”，保留可查看状态的入口，就绪后显示可用地址，失败给出原因与修正/重新提交路径并保留适用输入。

**改善与边界**：首次任务只承担必要决策，熟练用户仍能找到高级能力，异步结果如实反馈。默认值需由项目证明有效；没有默认值时先提供选择或前置配置入口，不能编造资源、费用或可用性保证。草稿不持久化密钥，恢复时重新验证环境与权限。

**验证**：新用户可走通默认创建；高级用户能查找并修改非默认项；请求受理不显示就绪；失败后输入可恢复，目标环境清楚；键盘可完成路径，窄屏主要动作与关键影响信息仍可达。

<a id="f4"></a>

## F4：组合标准控件，复用同一领域合同

**场景与合同**：服务发布与模型服务创建都需要单选目标环境。两页共享环境 ID、名称与禁用原因语义，但请求入口和草稿所有者不同；项目已有 shadcn/ui Select。选择动作只更新草稿，不直接发布。

**Bad**：两页分别用 `div`、绝对定位菜单和点击监听手写选择器，各自 hardcode 样式与状态；之后复制为“共享组件”，组件内通过 pathname 猜测业务并请求环境列表。一处改键盘行为，另一处仍有缺陷；组件复用又绑定了路由与请求。

**Good**：在环境领域共享模块提供 `EnvironmentSelect`，组合本地 Select 与项目标准字段结构。接口示意如下，不是独立可运行组件：

```ts
type EnvironmentOption = {
  id: string;
  name: string;
  disabledReason?: string;
};

type EnvironmentSelectProps = {
  id: string;
  options: readonly EnvironmentOption[];
  value: string;
  onValueChange: (environmentId: string) => void;
  disabled?: boolean;
  loading?: boolean;
  error?: string;
};
```

两页的数据适配各自读取已授权环境，映射为 `options`，持有 `value` 并响应 `onValueChange`。共享控件统一标签、占位、尺寸、空/加载/错误与禁用原因，复用 Select 的键盘和焦点行为；契约规定环境 ID 非空，未选择时 `value` 为空串，列表加载中不能修改选择。调用方根据新列表判断已选项是否失效，传入 `error` 并阻止无效提交；控件保留当前值供用户修正，不能静默选第一个环境或触发发布。

**改善与边界**：一处维护相同交互，页面保留数据和副作用所有权；示意 API 沿用项目命名并按需要增加表单/ARIA 合同。授权由后端落实，前端提供的 `options` 不证明提交权限。多选、跨租户选择或允许创建环境时先检查语义差异；不要持续向单选接口添加模式开关。

**验证**：两页均可用鼠标与键盘选择；空列表、加载、禁用原因、错误及已选环境消失时行为符合合同，草稿不被自动改成其他环境。两页请求目标与权限参数正确，组件不请求业务 API，也不依赖 pathname。共享样式或接口变更后检查两处真实调用方。
