---
type: Architecture Decision
title: 复用宿主模型的本地全文检索
description: knowledge-maintainer 使用宿主已有模型理解问题，本地 QMD 纯全文索引负责无模型召回与文档变化对账。
tags: [knowledge-maintainer, qmd, rag, incremental-index]
status: stable
generated: { by: agent/codex, at: 2026-10-17T23:11:45+08:00 }
sources:
  - resource: /technical/research/qmd-evaluation-2026-10-17.md
    title: 固定 QMD 版本的研究与盲查询实验
  - resource: https://github.com/tobi/qmd/tree/facd35e01359e59d938bc9418e93fb9318addee3
    title: QMD 2.8.3 固定发布源码
---

# 复用宿主模型的本地全文检索

## 决策与适用范围

用户要求不依赖额外模型，复用当前已有模型，允许在宿主支持时使用便宜模型。knowledge-maintainer 因此采用“当前 Agent 规划关键词 → 本地纯全文召回 → Agent 筛选有限候选 → 校验并读取实时原文”的检索增强流程。原有分层 `index.md` 与无状态搜索保持可用。

固定 QMD 2.8.3 只承担全文索引。聊天模型不替代 embedding；本实现直接取消 embedding、自动扩展与模型重排步骤，不复制宿主登录凭据或新增推理 provider。规划默认在当前会话完成；便宜子模型仅在宿主已有能力且收益明确时按需调用，不成为运行前提。

## 实现合同

入口为仓库 `skills/knowledge-maintainer/scripts/context_kg_qmd.py`，工作流权威说明见 `skills/knowledge-maintainer/references/local-retrieval.md`。脚本依赖 Python 3.9+、已有 PyYAML 与固定 QMD，支持 macOS/Linux。

- 缓存按 bundle 隔离，位于 Git 仓库外，只是可重建派生物。每篇合法 concept 对应一个 ASCII 文件名投影，保留原始路径和全文；本次不引入另一个切段引擎。普通 `index.md`、`log.md` 由导航直接消费。
- 源文件全文 SHA 决定变化，只重新解析和写入变动 concept。清空、无效 frontmatter 或缺少 type 会移出旧候选并警告；源目录、根索引或读取故障与合法删除区分，失败不发布新 manifest。
- 同步与查询持独占缓存锁。改投影前记录 dirty，QMD 更新成功才原子发布 manifest；中断后重新对账和修复投影，再允许查询。没有跨文件的原子快照保证。
- 查询前主动对账，最多 4 条宿主规划查询，本地合并并在候选上限前应用 scope/type/status 过滤。普通查询排除 deprecated 和 Session Summary；精确路径/标题/ID 有元数据补召回。
- 输出仅含有限元数据和短片段，完整 JSON 有字符预算。候选返回和原文读取均核验源文件 SHA；相关性分数不替代时效、来源与生命周期判断。大文件通过有界分页读取。
- 监听是显式启动的前台轮询：启动对账、stat 变化去抖、周期全文 hash 补查。根暂时消失或更新失败时报告错误并重试，不注册系统服务。
- QMD 配置、运行目录和缓存隔离，模型来源指向不可用本地文件。调用白名单仅有版本查询、全文搜索与维护命令；缺依赖、版本不符或更新失败明确报错，调用者可以选择无状态搜索。

## 取舍与验证边界

纯全文引擎不会自行理解中文同义表达，召回依赖当前 Agent 的关键词规划；有限候选也可能完全不能回答问题。至少核对候选原文及其来源后才作答。历史研究中的向量/批量模型实验不是本适配层的准确率或性能验收。

查询前完整 SHA 对账需要本地读取语料，换取同大小、恢复 mtime 修改的可见性；这不是只靠 mtime 的零扫描查询。QMD CLI 会产生进程启动和多路搜索成本，不能直接沿用常驻 HTTP 的耗时。当前不承诺端到端速度、固定 token 节省、模型费用或生产 SLO。

实现与运行检查记录在 [任务 Review](/tasks/todo.md)，真实 QMD 集成用例位于仓库 `skills/knowledge-maintainer/tests/test_context_kg_qmd.py`。缺真实 QMD 时这些集成用例会明确跳过，跳过不等于验证通过。
