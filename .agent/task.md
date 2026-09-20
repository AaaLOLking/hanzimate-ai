# 当前任务

（2026-09-20 更新）连续会话/工具/前端重构/HSK 知识库（含高等级扩展与策略硬化）均已完成并验收（见 progress.md）。

**当前进行：UX 流程改进三项**（计划 docs/architecture/ux-flow-improvements.md，用户已确认全部推荐方案）：
1. 修复「对话训练」死导航——新建 /practice 独立选模式页（场景/自由/自定义三卡片）；
2. 结束流程插入「本次回顾」步骤——报告笔记 + 候选错误逐条勾选收入错误本；错误本新增按日期分组视图；
3. 零依赖轻量 i18n（zh/en），范围=AppShell 导航 + 首页 + /practice 页。

单个前端代理顺序实施，检查点 .agent/ux-progress.md；不改后端 API 合同、无新依赖、不 git commit。约束沿用惯例。
