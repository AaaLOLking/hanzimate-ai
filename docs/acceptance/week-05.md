# Week 5 验收清单

> 范围：会话报告、候选错误决策、结构化长期错误记忆与下一次会话召回。

## 自动验收

- [x] 已完成会话可幂等生成一份结构化报告，未完成会话返回 409；
- [x] 报告包含任务结果、最多 3 个亮点、最多 3 个候选错误、下一步、模型与 Skill 版本；
- [x] 模型输出在持久化前通过强类型合同，并由服务端强制保持 `candidate`；
- [x] 用户确认后才按 `user_id + canonical_key` 创建或更新 `ErrorCluster`；
- [x] 用户驳回的候选不会进入长期记忆，最终决策不可反向覆盖；
- [x] 新对话最多召回当前用户最近 5 个 `active` 错误簇；
- [x] 归档错误簇后，下一次 Context Pack 不再包含该记忆；
- [x] 会话报告、错误事件、错误簇和决策 API 均强制按用户隔离；
- [x] DeepSeek API Key 只在后端 Authorization Header 中使用，不进入模型结果或浏览器；
- [x] 无 DeepSeek 凭证时明确记录 `local / rule-summary-v1`，不伪装成真实模型。

## 验收证据

- API：21 个 pytest 用例通过，其中 5 个新增用例覆盖报告幂等、确认/驳回、召回/归档、跨用户隔离和 DeepSeek JSON 请求合同；
- 数据库：全新 SQLite 从 `0001 → 0004` 成功，`alembic check` 无漂移；本地已有表只在只读结构比对一致后对齐版本号；
- 教学 Skill：`validate_skill_assets.py` 通过，错误分类、候选状态与会话总结 Schema 保持有效；
- Web：ESLint、TypeScript 与 Next.js 生产构建通过，新增会话报告和 `/errors` 错误本；
- 浏览器：本地完成“食堂点餐 → 输入‘给我一个水’ → 结束 → 生成报告 → 确认 → 错误本”全链路；报告标记为 `local / rule-summary-v1`，刷新后决策状态仍在；
- 召回：确认后创建的新会话 Context Pack 含 `lexical:measure-word:水:瓶` 和“给我一瓶水”，Session Instructions 明确仅在相同模式复发时提醒；
- 运行质量：浏览器控制台 0 error / 0 warning，验收链路 API 全部返回 2xx；
- 截图：`output/playwright/week-05/week-05-session-report.png`、`output/playwright/week-05/week-05-error-book.png`（本地产物，不进入版本控制）。

## 本轮明确不冒充完成的部分

- 当前结构化 Top-5 召回不是 pgvector 混合检索；Recall@5、Precision@5 与 p95 尚未测量；
- 未配置 DeepSeek 凭证，真实 `deepseek-v4-flash` 的 20 个种子案例精度、延迟与费用尚未验证；
- FSRS 复习卡、用户自定义间隔和定期任务属于下一条纵向切片；
- 候选错误后端支持覆盖正确表达，但本轮 Web 尚未提供行内编辑器。
