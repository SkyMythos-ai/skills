---
type: Lesson
title: 技能维护经验
description: 记录修改 Skill 时需要持续遵守的可复用规则。
tags: [skill, maintenance]
status: stable
generated: { by: codex/gpt-5, at: 2026-08-22T00:00:00+08:00 }
---

# 技能维护经验

- 用户指定技能新名称时，同步更新目录名、SKILL frontmatter、界面元数据、默认提示、命令示例及知识库引用，并验证旧名称无残留。
- 设计知识库 taxonomy 时，将可复用测试用例、测试用例编码规范和代码设计规范视为一等长期知识，分别建立独立权威 concept，并与缺陷复盘、测试策略、ADR 和任务记录清晰分离。
- 维护知识库时同时设计快速渐进检索、按影响面增量更新和会话结束摘要；摘要只做连续性导航，长期结论仍回写唯一权威 concept，临时交接遵守 `.handoff/` 规范。
