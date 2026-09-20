# 课程作者与发布规范

## 1. 当前基线

课程内容的权威源是 `apps/api/app/content/course_catalog*.json` 中的不可变发布目录，由后端在启动时通过严格 Pydantic 合同校验并写入版本表。v1 保留 3 节验证课；当前 v2 包含 6 节生活/校园沟通课与 6 节 HSK 2–4 能力课。API 目录只展示每门课的最新版本，旧课节仍可通过历史 Workspace 和不可变 lesson ID 恢复。

教学设计以教育部发布的《国际中文教育中文水平等级标准》（GF0025-2021）为能力框架。该标准采用“三等九级”，可用于国际中文教育的教学、学习、测试与评估，并作为 HSK 命题参考。2026 年新发布内容使用中文考试服务网的 [HSK3.0 官方页面](https://www.chinesetest.cn/HSK)和[新版 HSK 考试大纲](https://hsk.cn-bj.ufileos.com/3.0/%E6%96%B0%E7%89%88HSK%E8%80%83%E8%AF%95%E5%A4%A7%E7%BA%B21219.pdf)；旧 v1 继续保留历史 `current-hsk-1-6` 标签，不回写版本。框架原文见[教育部标准信息页](https://www.moe.gov.cn/jyb_sjzl/ziliao/A19/202111/t20211118_580755.html)。

## 2. 单课合同

每课必须满足：

- 一个可观察目标，学习者完成后能说出、写出或辨认具体产物；
- 预计 5–20 分钟，当前产品目标为 8–15 分钟；
- 至少一个能力目标和一个可追溯来源；
- 一段必要知识说明与至少两个例子；
- `guided_practice`：允许查看知识和提示；
- `retrieval_practice`：默认隐藏知识，要求从记忆产出；
- `transfer_task`：换到新场景，验证能否迁移；
- 明确的完成证据与下一次复习建议。

公开内容只包含题目、说明、例子和来源。`answer_rule` 与 `assessment_config` 只保存在服务端，不能下发浏览器，避免把答案规则暴露给学习者。

## 3. 版本规则

- `CourseVersion` 与 `LessonVersion` 一经发布即不可变；
- 修改标题、目标、来源、正文、评分规则或课节集合，都必须创建新的课程版本；
- 修改单课时增加 `lesson.version`，生成新的 `lesson.id`，旧进度仍指向旧版本；
- 后端对课件正文与评分配置计算 SHA-256；哈希变化或课节集合变化会拒绝启动；
- v1 的 3 节课和 v2 的 12 节课分别是完整集合；不得向任何已发布版本原地追加；
- `track` 从 v2 起必填，只允许 `daily-life` 或 `hsk`；
- 每个课程目录保留生成它的 Skill 版本，v2 使用 `chinese-learning-coach` v0.2.0。

## 4. 学习与提问边界

每次进入课节都创建或恢复唯一的 `LessonProgress + Workspace`。课程导师只接收：

- Mission 摘要、辅助语言和估计等级；
- 当前课节 ID、版本、目标、知识、例子与来源；
- 最多 3 条与本课相关且已确认、仍 active 的错误模式；
- 当前课节最近 6 条消息；
- “不确定就说明、拒答课外问题、引用本课来源”的策略。

不得注入完整聊天历史、其他课节消息、候选或已驳回错误。无 DeepSeek 凭证或调用失败时，系统明确标记 `local / lesson-context-v1`，不伪装成在线模型。

## 5. 发布检查

1. 为所有事实性教学主张登记来源，确认可引用范围，不复制无授权教材正文或试卷；
2. 运行 API 测试，验证合同、顺序、权限、证据与版本锁；
3. 运行核心 Skill 资产校验；
4. 执行 `alembic upgrade head` 与 `alembic check`；
5. 运行 Web lint、类型检查和生产构建；
6. 在真实浏览器完成一次失败重试、三阶段通过、刷新恢复和课内提问；
7. 保存验收截图与模型/Skill 版本，不用 mock 结果替代真实 Provider 指标。

发布前运行：

~~~powershell
uv run --project apps/api python packages/chinese-learning-coach/scripts/compile_course_wiki.py --catalog-dir apps/api/app/content --check
uv run --project apps/api python packages/chinese-learning-coach/scripts/compile_course_wiki.py --catalog-dir apps/api/app/content --output-dir docs/course-wiki
~~~

编译器会检查跨版本 ID、课节顺序、来源、轨道、三阶段活动与评分规则，生成不含 `answer_rule` 和 `assessment_config` 的 Markdown Wiki 以及 SHA-256 清单。
