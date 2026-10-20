# 本地全文检索

适用于已启用本地索引、较大的知识库，或用户要求快速检索与文档监听的场景。当前 Agent 负责关键词规划、候选筛选和证据判断；`scripts/context_kg_qmd.py` 仅做本地文件对账与 QMD 全文搜索。更换聊天模型无需重建索引。此路径不调用 embedding、扩展或重排模型，不配置推理 API，不读取宿主登录凭据。

## 准备与边界

需要 Python 3.9+、PyYAML、macOS/Linux，以及固定 `@tobilu/qmd@2.8.3` 的可执行文件。首次使用先检查依赖；缺失时明确说明并使用原有 `context_kg_search.py` 完成候选定位，不能把 QMD 故障解释成无答案。安装依赖属于显式准备操作，不在查询中自动下载：

```bash
python3 -m pip install pyyaml
npm install -g @tobilu/qmd@2.8.3
```

下列命令从目标项目根目录运行；将 `<skill-dir>` 替换为当前 Skill 实际目录，不依赖固定宿主安装位置。非 PATH 中的 QMD 用全局选项 `--qmd /absolute/path/to/qmd` 指定。缓存默认放在 `$XDG_CACHE_HOME/knowledge-maintainer/qmd/` 或 `~/.cache/knowledge-maintainer/qmd/` 的 bundle 独立目录；`--cache-dir /outside/repository/cache` 可显式指定，必须在 bundle 与 Git 仓库外。缓存中的原文投影与索引可能包含私有知识，按原文权限管理，不能作为知识来源或提交到 Git。

```bash
python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg sync
python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg status
```

`sync` 只索引普通 concept，保留文件 `index.md`、`log.md` 仍由渐进导航读取。适配层在私有缓存内创建 ASCII 路径投影，保留原始路径映射；配置与运行目录均隔离。QMD 只运行全文维护与搜索命令，模型路径指向不可用的本地文件。QMD 提示待 embedding 不代表全文索引失败。

## 单次查询

1. 按主 Skill 读取根索引并确定子意图、精确键、范围、类型和时间语义。直接在当前模型中生成 1–4 个简短查询，各查询内空格连接必要词，查询之间表达同义或不同子意图；保留 Case ID、符号、路径与中英别名。例如“重复扣款如何防止”可规划为 `支付 幂等`、`扣款 去重`，而不是直接把长问句交给全文引擎。首次无需专门调一次便宜模型。
2. 运行一次有预算的本地搜索。`--alternative` 可重复，所有查询最多 4 条；默认最多 5 个候选，允许扩到 20，整个 JSON 默认不超过 12,000 字符。范围、类型、状态过滤发生在输出候选上限之前：

   ```bash
   python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg search "支付 幂等" \
     --alternative "扣款 去重" --scope business --limit 5
   python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg search "TC-ORDER-042" \
     --type "Test Case" --max-chars 6000
   ```

3. 根据 `path/title/description/tags`、短片段和 `matched_queries` 选择 1–3 篇原文。`score` 只表达召回顺序，`status/freshness` 与原始来源决定可信度；`draft` 或已过期内容须核验。默认排除 deprecated、任意层级的 archive 目录与 Session Summary。`--status deprecated` 可查非归档的弃用页，归档页和 Session Summary 使用 `--history`。
4. 使用候选的 `sha256` 和 `start_line` 有界读取实时原文。Hash 不符时重新搜索；不要让缓存片段替代证据：

   ```bash
   python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg read business/payment.md \
     --start-line 12 --lines 60 --expected-hash <candidate-sha256>
   ```

   每次最多 120 行，完整 JSON 默认受 6,000 字符预算约束。`has_more` 为真时，将 `next_line` 传给下一次的 `--start-line`、`next_column` 传给 `--start-column`，并保持同一 `--expected-hash`；行内列偏移从 0 开始，按字符计数。这样超长单行也能连续读取，不会反复返回前缀或跳过被截断的内容。必要时沿原文链接读取一跳证据，按主 Skill 的停止条件结束。
5. 零候选时，先检查是否为依赖/同步失败，再调整词语或扩大 scope。多词 AND 组合可能过强：下一轮先拆为最多 4 个独立主题词或精确键分别查询，例如 `退款 幂等` 无结果时尝试 `退款`、`幂等`，由当前 Agent 筛选近邻，不把所有扩展词继续堆进同一个 AND。查询改写最多额外两轮；有候选但不能覆盖问题也应说明缺少证据。`candidates=[]` 与非空近邻都不能自动决定答案。宿主支持且收益明确时，可让已有的便宜子模型只查看问题与有限候选；选择模型和认证由宿主承担，主 Agent 复核原文，不能把新模型设成必需依赖。

## 文档变化与监听

写入 concept 并完成 lint 后主动执行 `sync`。同步对源文件全文计算 SHA，仅重新解析和写入变动 concept，删除、改名或清空会移除旧投影。没有变化时跳过 QMD 更新。每次 `search` 也先对账，未开启 watcher 时仍能发现同大小、恢复 mtime 的改写。

持续编辑时可显式启动前台监听：

```bash
python3 <skill-dir>/scripts/context_kg_qmd.py ./context-kg watch \
  --interval 1 --debounce 0.4 --reconcile-seconds 30
```

首次启动对账，stat 轮询变化后去抖更新，定期全文 hash 补查漏变更；Ctrl-C 退出。该命令不注册系统后台服务，Agent 不为一次问答留下常驻进程。变化检测与索引更新均不调用模型。

同步与查询共享 bundle 缓存锁；更新前标记 dirty，成功后原子发布 manifest，失败或中断后由下一次同步恢复。根目录或根 `index.md` 消失、扫描读取失败时保留旧缓存并报错，查询不会把旧缓存当当前证据；watcher 保持前台并重试，恢复后重新对账。空文件或无有效 frontmatter/type 的文件暂时移出索引并警告，修复后再同步。没有跨文件同一时刻的快照保证，读取时仍须核验单文件 hash。

## 故障与恢复

- 缺依赖、版本不符、锁超时、QMD 失败或源 hash 不符：命令非零退出，保留具体错误；按需改用无状态脚本，不静默返回空候选。
- 缓存是可丢弃派生物。损坏时停止使用它，显式选择一个新的仓库外 `--cache-dir` 后 `sync` 重建；不要删除原文或权威 `index.md`。
- 此路径以全文关键词召回，中文同义表达依赖当前 Agent 规划。候选预算限制上下文体积，不承诺固定 token 节省、通用中文准确率或端到端延迟。
