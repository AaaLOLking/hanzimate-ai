# HanziMate Live v1 开发循环记录

验收文件：`docs/acceptance/live-voice-v1-development.md`  
开始日期：2026-09-08  
迭代上限：15 轮

## 第 0 轮：基线锁定

- 已读取现有项目结构、实时语音设计书、Web 目录规则及已安装 Next.js 的客户端组件说明。
- 仓库当前没有初始提交，所有项目文件均处于未追踪状态；保留现状并直接修改，不自动提交。
- 当前工作区没有 `.env` 或 `apps/web/.env.local`，真实 Qwen 协议与真机体验不能在本机验收。
- 开发基线：现有语音后端专项测试 10 项通过（2026-09-05 运行记录）；本轮完成后重新执行全套检查。

结论：进入第 1 轮，实现 live-v1 数据与 API 合同。

## 第 1 轮：Live v1 数据与 API

- 为语音会话加入 `client_session_id`、协议版本、配置版本、连接代次、传输状态、截止时间、结束原因和 closing manifest。
- 为转写加入 Provider 条目标识、连接代次、终稿状态和播放完成／打断状态。
- 新增幂等创建、配置更新、播放状态更新、ending 排空与 finalize 对账接口。
- Qwen 会话配置按纠错模式、语速、耐心档位和辅助语言生成；语义 VAD 能力在真机实验前保持 `unverified`。
- 会话总结只读取最终可靠转写。
- 新增迁移 `20260908_0009`，完成空库升级、降级、再升级和 schema drift 检查。

结果：专项语音测试 14 项通过，进入前端连接与交互实现。

## 第 2 轮：实时连接与聚焦通话界面

- 将 Provider 事件解析、WebRTC 传输、音量检测和正交运行状态拆到 `apps/web/features/live/`。
- WebRTC 仅在 Peer、DataChannel 与 `session.updated` 均确认后进入 active；重连递增 connection epoch，旧 epoch 事件直接丢弃。
- 实现双方流式字幕预览、可靠终稿保存、静音、停止回答、文字输入、字幕记录抽屉、语速与停顿耐心热更新。
- 结束流程先冻结已知事件清单，再关闭媒体、等待在途写入并对账；不完整记录必须由用户明确选择后才能结束。
- mock 模式固定显示“本地模拟／本地演练”，不冒充 Qwen 实时连接。

结果：TypeScript、ESLint 与生产构建通过，进入浏览器验收。

## 第 3 轮：浏览器与全量验收

- 用 Playwright 在 Chrome 内完成建档、进入对话、本地演练、文字发送、字幕展开、结束保存和报告展示。
- 视觉检查确认核心通话状态、字幕和四个控制入口位于主舞台；本地模拟标识清楚。
- 浏览器验收发现旧 SQLite 缺少新增列，已执行迁移并在 README 增加现有数据库升级步骤。
- 修复“再练一次”计时未归零、Provider 预览与终稿 ID 变化导致孤立清单、重复 delta 写入重复遥测、旧连接晚到回调串入新 epoch 等问题。

硬检查（2026-09-08）：

- `uv run --project apps/api pytest apps/api/tests`：64 passed。
- `uv run --project apps/api ruff check apps/api/app apps/api/tests apps/api/alembic`：通过。
- `pnpm lint:web`：通过，0 warning。
- `pnpm typecheck:web`：通过。
- `pnpm build:web`：通过，10 个页面完成构建。
- `uv run alembic check`：No new upgrade operations detected。

软验收：

| 维度 | 得分 | 证据 |
|---|---:|---|
| 通话清晰度 | 9/10 | 浏览器主流程可直接识别开始、停止回答、字幕、文字输入和结束入口 |
| 状态真实性 | 9/10 | lifecycle、transport、input、output、persistence 独立建模；active 等待配置确认 |
| 学习体验 | 9/10 | 三种纠错模式、双语上下文、慢速与耐心停顿进入服务端教学配置 |
| 可靠性 | 8/10 | epoch 隔离、两次重连、清单排空和显式不完整收尾已覆盖；真机断网仍待凭证环境 |
| 可维护性 | 8/10 | 事件、传输、音频与状态已拆分；会话编排仍集中在路由页面，后续可继续提取 hook |
| 数据可信度 | 9/10 | partial 不入库，Provider 去重，终稿、播放打断与缺失记录语义明确 |

结论：无需供应商凭证的 Live v1 基础版本验收通过。唯一剩余项为 `BLOCKERS.md` 所列真实 Qwen G1–G7 与真机指标。

## 第 4 轮：刷新恢复与失联会话回收

- 新增会话恢复合同：刷新后从工作区恢复活动会话、可靠转写、连接代次、配置和已用时长；恢复提示不会自动申请麦克风。
- 用户可选择重新接入语音、改用文字续接或直接结束；文字续接保留原有记录，不重复生成欢迎语。
- 活动通话与恢复提示页每 15 秒发送心跳；后端后台任务每 30 秒扫描，90 秒失联或超过练习截止时间的会话进入可恢复的 ending 状态。
- 修复 SQLite 无时区 UTC 时间在浏览器中按本地时间解析的问题，恢复后的计时与服务端一致。
- Playwright 覆盖两条路径：失联会话刷新后完成保存，以及活动会话刷新后用文字继续、保持单条欢迎语、再结束保存；控制台 0 error。

硬检查（2026-09-08）：

- `uv run --project apps/api pytest apps/api/tests`：66 passed。
- `uv run --project apps/api ruff check apps/api`：通过。
- `pnpm lint:web`：通过，0 warning。
- `pnpm --filter web exec tsc --noEmit`：通过。
- `pnpm build:web`：通过，10 个页面完成构建。
- `uv run alembic check`：No new upgrade operations detected。

结论：刷新恢复、前台心跳和后台失联回收已完成；当前剩余阻断仍只有真实 Qwen G1–G7 与真机指标。

## 第 5 轮：真实浏览器协议探测（2026-09-16）

- 凭证已进入本地 .env，模板中对应凭证已清空。
- Chrome 153 经现有后端完成真实 SDP、ICE、DTLS 和双 DataChannel 连接，收到 session.updated。
- 验证 AI 字幕 delta/done、入站音频包、停顿参数热更新和 response.cancel 的 cancelled 终态。
- 项目已有远端 txt 数据通道监听，无需针对本次探测修改传输代码。
- 取消后仍有字幕继续到达；未测试实际音频播放或麦克风，不宣称自然插话或打断延迟达标。
- 诊断连接和会话已关闭；完整证据及 G1–G7 剩余项见 docs/spikes/002-qwen-browser-probe.md。

结论：凭证和浏览器协议链路已经打通；进入真人语音体验与异常恢复验收，能力全局声明继续保持 unverified。

## 第 6 轮：自由对话与自定义目标（2026-09-16）

- 用户确认真人基础通话可正常使用，选择暂缓打断专项验收，转向自由与自定义练习。
- 新增 scenario/free/custom 三种练习方式。自定义目标去除首尾空白并限制 500 字，空目标及矛盾字段返回 422。
- 目标和模式进入工作区与会话 context_pack；实时指令、恢复合同、现有报告生成沿用本次目标，无需数据库迁移。
- 创建幂等比较模式与自定义目标，场景标识从会话快照读取，避免工作区后续切换影响旧会话重试。
- 前端新增模式选择、目标输入及校验；刷新恢复和重新练习保留模式与目标。自由/自定义本地演练不再套用校园问路回复，并明确提示真实回应需实时模型。
- 测试夹具显式隔离本地凭证，修复配置真实 Key 后 mock 回归测试误入供应商路径的问题。
- 后端全量 73 项测试、Ruff、Web ESLint 和 TypeScript 通过。浏览器验证了空目标禁止开始、自定义目标开始/刷新/结束保存、自由模式欢迎语和结束保存，控制台 0 error。
- 本轮未重新验收自由/自定义模式的真人教学效果，打断专项验收仍保留待办。
- Next.js 生产构建通过；已重新启动本地前后端供用户体验。

## 第 7 轮：连续会话与工具 Agent 交接（2026-09-17，未验收）

用户要求先保存讨论与开发状态，再压缩上下文，功能开发暂在此处停下。

详见 [连续会话、记忆与工具 Agent 决策记录](docs/architecture/continuous-memory-and-tools.md)。记录包含产品方向、八分钟与上下文限制、连续会话已写代码及缺口、工具调用设计、验证基线和恢复开发检查清单。

本轮已编写 continuous 会话标志、服务端历史摘录、resume 注入、前端分段续接和 Markdown 导出；尚未完成后端回归、最终构建和跨段浏览器验收，不应视为已交付。工具调用、HSK 检索、联网搜索和独立问答模型均尚未实现。已读取中断前 TypeScript 与 ESLint 进程，退出码均为 0。
