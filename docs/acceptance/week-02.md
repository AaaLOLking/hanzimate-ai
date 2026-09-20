# Week 2 验收清单

> 范围：账户边界、Consent、Mission、初步画像、工作区与 Model Registry。

## 自动验收

- [x] 新用户读取建档状态为 `complete=false`；
- [x] 用户提交建档后持久化 Consent、Mission 与 Learner Profile；
- [x] 建档自动生成一个与首要目标相关的推荐工作区；
- [x] 刷新后能列出并恢复该工作区状态；
- [x] 工作区查询强制按 `user_id` 隔离；
- [x] 未明确接受隐私条款不能完成建档；
- [x] Model Registry 只向用户展示已启用的模型；
- [x] Alembic 初始迁移可以在空数据库上升级到 head；
- [x] Web lint、类型检查和生产构建通过；
- [x] 浏览器完成一次建档到首页恢复的真实链路，控制台零错误。

## 验收证据

- API：6 个 pytest 用例通过，其中包含 3 个并行首页请求的身份初始化回归测试；
- 数据库：全新 SQLite 数据库 `alembic upgrade head` 与 `alembic check` 均通过；
- Web：ESLint、TypeScript 与 Next.js 生产构建通过；
- 浏览器：`PUT /api/v1/onboarding`、刷新后的列表读取、`GET /api/v1/workspaces/{id}` 均返回 200，控制台 0 error / 0 warning；
- 截图：`output/playwright/week-02-dashboard.png`（本地产物，不进入版本控制）。

## 当前认证约束

Web MVP 使用 `X-Learner-ID` 作为开发身份适配器。开发环境缺省进入固定 demo 用户；生产环境必须提供已认证身份，且未知账户返回 401。正式邮箱登录接入时，只替换这一层，不改变建档与工作区 API。
