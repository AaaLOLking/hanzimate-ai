# Week 7 验收清单

> 范围：完整 12 节课程 v2、多版本发布、课程 Wiki 编译与 Chinese Learning Coach Skill v0.2.0。

## 自动验收

- [x] v2 包含 12 节课，严格分为 6 节 `daily-life` 与 6 节 `hsk`；
- [x] 每课只有一个可观察目标、5–20 分钟、至少两个例子、三个产出阶段和来源；
- [x] v1 三节课保持不可变并继续可访问，v2 使用新的 course-version 与 lesson-version ID；
- [x] 课程列表对每个 course 只返回最新发布版本，历史课节 URL 和 Workspace 不失效；
- [x] 12 节课的浏览器响应均不包含 `answer_rule` 或 `assessment_config`；
- [x] HSK 写作课只有完成迁移任务才产生 completed 状态；
- [x] Skill v0.2.0 新增课程发布路由、版本规范与确定性编译器；
- [x] 编译器检查跨版本身份、顺序、来源、轨道、活动与评分规则；
- [x] 课程 Wiki 共 15 个课节页并生成 SHA-256 manifest，公开页不编译答案规则。

## 验收证据

- API：`pytest` 29 项全部通过；课程列表只暴露 v2，v1 课节详情仍可按历史 ID 访问，12 节课均验证不泄露服务端评分规则；
- 数据库：v1/v2 共 2 个课程版本、15 个不可变课节版本；无新表，Alembic 保持 `0005 head`；
- Skill：`validate_skill_assets.py`、课程编译器 check 与 `skill-creator/quick_validate.py` 通过；
- 来源：能力框架依据教育部 GF0025-2021；v2 考试范围引用中文考试服务网 HSK3.0 页面与新版官方考试大纲，旧 v1 标签保持不变；
- Web：ESLint、TypeScript 与 Next.js 生产构建通过；真实浏览器完成“目录 → 第 12 课 → 课内提问 → 三阶段产出 → 刷新恢复 → 返回目录”链路，目录由 `0/12` 更新为 `1/12`；
- 浏览器网络：15 个业务请求全部为 2xx；控制台 0 error / 0 warning；
- 截图：`output/playwright/week-07/week-07-course-v2-catalog.png`、`week-07-hsk-writing-complete.png`、`week-07-course-progress.png`。

## 本轮明确不冒充完成的部分

- 12 节课已通过合同、确定性评分与浏览器链路验收，但尚未经过真实中文教师逐课签名评审；
- 当前评分仍是可审计关键词基线，不能等同开放回答语义评分；
- 未配置 DeepSeek 凭证，真实课内问答质量、延迟和费用仍未验证；
- Wiki 是版本化课程知识层，不替代用户证据、错误状态或后续向量语义召回；
- FSRS、复习偏好和提醒队列按路线图进入 Week 8。
