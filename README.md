# HanziMate AI

面向来华留学生的 HSK 与日常中文学习 Agent。

当前已完成 Web MVP 的 Week 9 质量与数据控制：新增学习档案页，用户可查看真实学习统计、修改长期错误记忆、下载个人数据或双重确认后删除账户。课程答疑和对话总结会记录 AI 来源与状态，达到每日上限或在线服务失败时自动使用本机规则。Week 8 的定期复习、12 节课程和核心教学 Skill v0.3.0 均保留。

## 目录

- apps/web：Next.js 学习工作区
- apps/api：FastAPI 业务与 Agent API
- packages/chinese-learning-coach：核心教学 Skill
- docs：PRD、信息架构、系统设计与验收记录
- infra：本地基础设施配置

## 本地启动

实时练习支持三种方式：场景练习、自由对话、自定义目标（最多 500 字）。自由对话跟随学习者的话题，自定义目标用于指定角色与练习需求；目标会随会话保存，恢复连接和学习报告沿用本次目标。使用麦克风入口连接真实实时模型，“先用文字演练”仍是本地演练入口。

需要 Node.js 24+、pnpm 11+ 与 `uv`。默认不复制根目录 `.env` 时，API 使用本地 SQLite 并自动建表，因此无需 Docker 即可体验完整建档流程。

前端：

~~~powershell
pnpm install
pnpm dev:web
~~~

后端：

~~~powershell
uv sync --project apps/api --extra dev
uv run --project apps/api uvicorn app.main:app --reload
~~~

### 需要自行配置的密钥

复制根目录 `.env.example` 为 `.env` 后按需填写。`.env` 已被 `.gitignore` 排除，不会进入版本库。

| 键 | 必需性 | 用途 | 获取 |
|---|---|---|---|
| `DASHSCOPE_API_KEY`、`DASHSCOPE_WORKSPACE_ID` | 语音通话必需 | 实时语音模型（阿里云百炼，qwen3.5-omni-flash-realtime） | [阿里云百炼控制台](https://bailian.console.aliyun.com/) |
| `DEEPSEEK_API_KEY` | 可选 | 独立问答工具、课程答疑、会话报告 | [DeepSeek 开放平台](https://platform.deepseek.com) |
| `TAVILY_API_KEY` | 可选 | 联网搜索工具 | [Tavily](https://tavily.com) |

不配置 DeepSeek 时课程答疑与报告明确使用本地降级模型；不配置 Tavily 时搜索工具明确返回「暂不可用」；不配置 DashScope 时实时练习进入本地演练模式。HSK 考纲检索（`hsk_lookup`）为本地知识库，无需任何密钥。

已有本地数据库在拉取新版本后需要先升级结构：

~~~powershell
Push-Location apps/api
uv run alembic upgrade head
Pop-Location
~~~

前端调用地址可复制 `apps/web/.env.example` 为 `apps/web/.env.local` 后调整。默认值已经指向 `http://localhost:8000`。

如需切换到 PostgreSQL，复制根目录 `.env.example` 为 `.env`、启动 `infra/compose.yaml`，然后执行：

~~~powershell
Push-Location apps/api
uv run alembic upgrade head
Pop-Location
~~~

健康检查：

- Web：http://localhost:3000
- API：http://localhost:8000/healthz
- API 文档：http://localhost:8000/docs
- 首次建档：http://localhost:3000/onboarding
- 对话训练：从首页工作区点击“开始对话”
- 系统课程：http://localhost:3000/courses
- 错误本：http://localhost:3000/errors
- 今日复习与个人节奏：http://localhost:3000/reviews
- 学习档案与个人数据：http://localhost:3000/profile

## 质量检查

~~~powershell
uv run --project apps/api pytest apps/api/tests
uv run --project apps/api ruff check apps/api/app apps/api/tests apps/api/alembic
pnpm lint:web
pnpm typecheck:web
pnpm build:web
~~~

Week 7 的详细出口条件见 [docs/acceptance/week-07.md](./docs/acceptance/week-07.md)，课程 Wiki 见 [docs/course-wiki/index.md](./docs/course-wiki/index.md)，课件版本与来源规则见 [docs/course-authoring.md](./docs/course-authoring.md)。课程导师和会话报告在没有 DeepSeek 凭证时都会明确使用本地降级模型，不会冒充真实模型；真实 Qwen WebRTC 仍需配置 DashScope 凭证。

Week 8 验收见 [docs/acceptance/week-08.md](./docs/acceptance/week-08.md)，复习与提醒边界见 [docs/review-scheduling.md](./docs/review-scheduling.md)。

Week 9 验收见 [docs/acceptance/week-09.md](./docs/acceptance/week-09.md)。模型费用单价默认留空，避免把过期价格当成事实；填写根目录 `.env` 中的单价后才显示估算费用。当前 MVP 不保存原始录音。

产品方案见 [AI中文学习Agent-Web-MVP项目计划书.md](./AI中文学习Agent-Web-MVP项目计划书.md)。

GPT Live 式实时语音交互的专项方案见 [HanziMate Live 开发技术设计书](./docs/architecture/realtime-voice-live-design.md)。**当前整体框架图**见 [docs/architecture/current-architecture.md](./docs/architecture/current-architecture.md)（2026-09-18 按代码实况绘制）。Live v1 基础版本已实现聚焦通话界面、静音与停止回答、双方字幕、连接代次隔离、幂等转写、排空后保存、刷新恢复与失联会话回收；没有 DashScope 凭证时会明确进入本地演练。真实 Qwen 协议与真机延迟仍按设计书 G1–G7 单独验收。
