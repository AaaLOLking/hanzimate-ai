# UX 流程改进实施检查点

日期：2026-09-20。执行：UX 改进代理（单代理顺序实施）。计划：docs/architecture/ux-flow-improvements.md（三个决策点用户已全按推荐确认）。

## 状态总览

| 项目 | 状态 | 验证 |
| --- | --- | --- |
| 1. /practice 选模式页 | 已完成（截图+流程验证通过，待统一验证） | lint/typecheck 绿；截图 0 控制台错误；自由对话文字流全链路通过 |
| 2. 结束后回顾 + 错误本日期化 | 已完成（E2E 通过，待统一验证） | lint/typecheck 绿；E2E：勾选→保存→PATCH→日期视图归档全通过，0 控制台错误 |
| 3. i18n MVP（导航+首页+/practice） | 已完成（E2E 通过，待统一验证） | lint/typecheck 绿；E2E：中英切换/持久化/无溢出/0 控制台错误 |

## 项目 1：/practice

状态：完成（2026-09-20）。

设计决策：
- `/practice` 为新建独立选模式页（用户已确认决策点 1）。三卡片（场景/自由/自定义）+ 场景列表（GET /api/v1/voice/scenarios）+ 自定义目标校验（custom 时空目标禁用开始）+ 纠错模式选择。
- 发起方式：POST /api/v1/voice/sessions **不带 workspace_id** → 后端为每次练习新建独立会话工作区（避免旧逻辑反复覆盖共享"日常中文"工作区状态），随后 router.push 到 `/conversation/[id]?join=voice|text`。
- 通话页新增 auto-join：仅当 URL 带 `?join=` 且恢复出的会话为全新（status created/connecting、0 条转写）时，走既有 resumeSession 路径自动进入通话（复用恢复卡同款函数）；不带参数行为完全不变（probe 安全）。参数消费后 history.replaceState 清除。
- 会话创建 payload 提取为共享 helper `apps/web/lib/practice.ts`（buildPracticeSessionPayload + isPracticeStartable），/practice 与通话页 startSession 共用，后端合同不变。
- 首页「开始对话」CTA 改为跳 /practice（未完成建档仍跳 /onboarding）；会话页内 startSessionCard 保留（服务"再练一次"与工作区恢复流程，双入口并存避免破坏实时链路）。
- navigation.ts「对话训练」href: null → "/practice"（AppShell 自动渲染为 Link）。

改动文件：
- 新增 apps/web/app/practice/page.tsx、apps/web/lib/practice.ts
- 改 apps/web/lib/navigation.ts、apps/web/app/page.tsx（CTA）、apps/web/app/conversation/[workspaceId]/page.tsx（join 逻辑 + payload 复用）、apps/web/app/globals.css（practice 样式段）

验证证据：
- pnpm lint:web 退出码 0；pnpm typecheck:web 退出码 0
- 截图 $TEMP/hanzimate-ux-shots/p1/practice.png：三卡片+六场景+纠错模式+0 控制台错误
- 流程探针 $TEMP/ux-flow-practice.cjs → p1-flow/join-text.png：/practice→自由对话→文字开始→自动进入通话页（liveComposer 可见，URL /conversation/3424f4db…?join=text），0 控制台错误

## 项目 2：结束后回顾 + 错误本日期化

状态：完成（2026-09-20）。

设计决策：
- 回顾粒度=逐条勾选（用户已确认决策点 2）。**默认全部不勾选**（显式 opt-in，符合教学 Skill 证据纪律；直接保存=全部忽略，比默认全选更保守，避免误收）。保存时逐条调既有 PATCH /errors/{id}（勾选→confirmed，未勾选→rejected），后端合同零改动；单条失败剩余保持 candidate 可重试。
- 报告区改为两段式：有待决候选→勾选清单+「将收入 N 条 · 忽略 M 条」+保存回顾；全部已决→只读状态（✓ 已加入错误记忆 / 已忽略）+ 收入/忽略计数条。转写 Markdown 导出入口保留（原有按钮未动）。
- 会话页新增 applySessionSummary 统一初始化 reviewSelections（恢复已保存报告同样进入只读态）。
- 错误本新增「按日期 / 按聚类」分段切换，**默认按日期**（用户痛点=无日期维度；新确认条目按发生日期即时归档可见）。日期视图数据=GET /errors?status=candidate + ?status=confirmed 合并（复用现有端点，两次请求），按 observed_at 本地日期分组倒序；rejected 不出现（计划要求）。每条含状态徽章（待确认/已确认）与「所属记忆」（按 cluster_id 匹配活跃聚类 corrected_example，缺失回退 subtype）；候选在日期视图内可直接确认/驳回（复用 decide()→loadMemory 刷新）。
- 聚类视图=原两节内容原样保留，切换到该视图才渲染。

改动文件：
- apps/web/app/conversation/[workspaceId]/page.tsx（reviewSelections/reviewSubmitting/submitReview/applySessionSummary + 报告 JSX 重写；移除即时双按钮与 decidingErrorId）
- apps/web/app/errors/page.tsx（view/dateGroups/confirmedEvents + 切换与日期视图 JSX）
- apps/web/app/globals.css（reviewItem/reviewSubmitBar/viewToggle/dateGroup/dateStatus 样式）

验证证据：
- pnpm lint:web 退出码 0；pnpm typecheck:web 退出码 0
- E2E 探针 $TEMP/ux-flow-review.cjs（真实 8000 后端，便利店场景文字流）：2 候选默认 0 勾选 → 勾选 1 保存 → decisionState=[✓ 已加入错误记忆, 已忽略]、计数条「收入 1 条 · 忽略 1 条」；/errors 日期视图 3 个日期组（09-20/09-18/08-24）状态正确；截图 p2-report-checklist.png / p2-report-saved.png / p2-errors-date.png；0 控制台错误
- 注：报告内容由 deepseek-flash 生成（英文）为模型行为，非本批改动范围

## 项目 3：i18n MVP

状态：完成（2026-09-20）。

设计决策：
- 零依赖 React Context + zh/en 字典（apps/web/lib/i18n/：index.tsx provider+useI18n、zh.ts 主键字典、en.ts 同键镜像）。t(key, vars?) 支持 {var} 插值；en 缺键回退 zh 再回退 key。
- 范围=导航+首页+/practice（用户已确认决策点 3）。导航 label 经 navLabelKeys 映射到字典（navigation.ts 仍管 icon/href/active key）；AppShell 品牌副标题、抽屉 aria、档案兜底文案同步 i18n。对话/错误本/课程等页保持中文（后续批次）。
- 切换器：侧栏底部 profileChip 上方（.langSwitch 分段控件），rail 通话专注模式收起（hover/focus 恢复显示）。localStorage 键 hanzimate-locale 持久化；provider 首渲染恒为 zh（与预渲染 shell 一致），挂载后异步对齐 localStorage，避免 hydration 不一致（react-hooks/set-state-in-effect 规则兼容）。
- 同步 document.documentElement.lang。布局溢出：EN 导航最长 "Error Book"/"Start conversation" 等在 264px 侧栏与卡片网格内无溢出（探针量 scrollWidth/clientWidth 均为 0 溢出）。

改动文件：
- 新增 apps/web/lib/i18n/index.tsx、zh.ts、en.ts
- 改 apps/web/app/layout.tsx（I18nProvider 包裹）、apps/web/components/app-shell.tsx（nav 翻译+切换器）、apps/web/app/page.tsx（全部文案 t() 化）、apps/web/app/practice/page.tsx（全部文案 t() 化）、apps/web/app/globals.css（.langSwitch 样式）

验证证据：
- pnpm lint:web 退出码 0；pnpm typecheck:web 退出码 0
- E2E 探针 $TEMP/ux-flow-i18n.cjs：zh 默认 → EN 即时切换（nav 全英文）→ /practice 导航可达且英文 → 刷新后 EN 持久（localStorage）→ 切回中文无残留；overflowEnHome/overflowEnPractice/overflowZhPractice 全部 0 溢出；lang 属性 zh-CN→en→zh-CN 正确；截图 p3-home-zh.png / p3-home-en.png / p3-practice-en.png / p3-practice-back-zh.png；0 控制台错误

## 统一验证清单（全部完成后）

- [x] pnpm lint:web —— 退出码 0
- [x] pnpm typecheck:web —— 退出码 0
- [x] pnpm build:web —— 成功（11 路由，含新 /practice；已按惯例先停 3000、build 后重启，现 3000 存活 200）
- [x] node --test apps/web/features/live/*.test.cjs —— 19 pass / 0 fail
- [x] uv run --project apps/api pytest apps/api/tests —— 115 passed in 29.55s（只跑不改）
- [x] Playwright 截图：/practice 三卡片、回顾勾选流、错误本日期视图、中英切换无溢出、0 控制台错误（$TEMP/hanzimate-ux-shots/ p1、p1-flow、p2、p3、final）
- [x] probe 复跑（8001 隔离）：continuous-browser-probe.cjs → PROBE_RESULT epoch=3/记忆/静音/导出全过 pageErrors:[]；continuous-browser-probe-end-during-rollover.cjs → endDuringRollover:true pageErrors:[]（四场景全过，通话页实时链路未受影响）。8001 已停止，3000/8000 存活。

## 遗留 / 说明

- 会话页 startSessionCard（选模式卡片）保留在通话页内，与 /practice 双入口并存：服务"再练一次"与工作区直接恢复流程，避免破坏已 probe 验收的实时链路（决策已记录项目 1）。
- 报告文本由 deepseek-flash 生成，语言为模型行为（本次观察到英文输出），不在本批范围。
- i18n 范围外页面（对话/错误本/课程/复习/档案等）保持中文，待后续批次；后端内容数据（场景标题/工作区名/复习卡标题）不按界面语言翻译（MVP 约定）。
- 日期视图「所属记忆」依赖活跃聚类匹配；聚类被归档后回退显示 subtype。
- 未 git commit（遵守约束）。探针脚本在 $TEMP（ux-shots.cjs / ux-flow-*.cjs / ux-final-sweep.cjs），未入仓库。
