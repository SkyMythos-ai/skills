# Skills 使用文档

这里集中说明仓库内各个 Skill 的适用场景、安装方式、调用示例和验证方法。

| Skill | 适用场景 | 详细文档 |
| --- | --- | --- |
| `knowledge-maintainer` | 维护符合 OKF 的项目知识库，包括查询、写入、代码反向生成、ADR、缺陷复盘、重组和校验 | [使用指南](knowledge-maintainer.md) |

## 文档约定

每个 `skills/<skill-name>/` 对应 `docs/<skill-name>.md`：

- 根 [README](../README.md) 只提供技能目录和快速安装入口。
- 本目录的索引帮助使用者选择合适的 Skill。
- 每个 Skill 的详情页说明适用与不适用场景、典型工作流、提示词和故障排查。
- `skills/<skill-name>/SKILL.md` 是 Agent 执行时读取的规范，不代替面向使用者的指南。
