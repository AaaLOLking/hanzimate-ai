# 前端结构重构进度（实施代理维护）

计划：docs/architecture/frontend-restructure-plan.md（已批准，四项决策全按推荐）。
执行者：前端重构子代理（唯一构建执行者）。状态：**全部三阶段已完成（2026-09-18）**。

## Phase 状态总览

- Phase 1 结构统一：完成
- Phase 2 动效与通话页适配：完成
- Phase 3 打磨（响应式/键盘/回归）：完成

## 交付内容

### 新文件
- apps/web/lib/navigation.ts — 单一导航数据源（7 项，档案图标 ◇→◈ 消歧）。
- apps/web/components/app-shell.tsx — 共享 AppShell：active/aria-current 导航、sidebar/panel 插槽、数据驱动 profile chip、rail 通话细条模式、窄屏抽屉（Escape/焦点圈/遮罩/ body 锁）。
- apps/web/components/panel.tsx — bento 卡片基元（raised/glass/interactive 变体）。

### 迁移页面（全部接入 AppShell）
首页（workspaceList→sidebar、coach→panel）、课程、课时（步骤→sidebar、课内老师→panel、stackColumn 定高滚动）、复习（promo→sidebar、节奏设置→panel）、错误本、档案、反馈、通话页（场景/纠错/隐私→sidebar、教练面板→panel、rail 收起）；onboarding 保持独立全屏。

### globals.css
token 分层（色板/阴影/圆角/动效时长+easing）；.appShell 两列默认/--panel 三列/--rail 细条（≥841px）/抽屉（≤840px）；pageIn 入场 + .reveal 滚动驱动（view()，range entry 40%——显式双命名区间触发 Chromium 解析 bug，单值写法规避并实测）；panelCard--interactive 悬浮；transcriptDrawer 玻璃；grid-template-rows: minmax(0,1fr) 使 .workspace 成为真正滚动容器（修复矮视口裁切隐患，view() 生效前提）；删除废弃 shell 类。

## 最终验证（全部通过）

- pnpm lint:web 退出 0（0 warning）；pnpm typecheck:web 退出 0。
- pnpm build:web 成功（10 路由）；build 前停 3000，build 后按惯例 Start-Process 重启（%TEMP%/hanzimate-web-dev.log，现 PID 62952）。
- node --test apps/web/features/live/*.test.cjs：19/19 通过。
- uv run --project apps/api pytest apps/api/tests：终跑 **104 passed**（首次全跑中 test_simultaneous_same_rating_commits_one_log 一次 409 时序抖动，单独重跑与两次全量重跑均通过；本代理未改任何后端代码）。
- probe 四场景（8001 隔离后端、合成音轨、不代表真人听感）：S1-3 epoch=3/duration=9/earlyMemory=true/mutedAcrossRollover=true/completed/export 200/pageErrors=[]；S4 endDuringRollover=true/epoch=2/completed/export 200/pageErrors=[]。
- 截图走查 %TEMP%/hanzimate-shots/final/：九页桌面 + 900/760 窄屏 0 pageerror/0 console error；基线在 baseline/。
- 交互回归：SPA 导航（首页→课程→课时）正常；通话页文字演练全程（开始→rail 收起→发送→结束→rail 恢复→报告）0 错误。
- 键盘：skip link 为首 Tab 停靠且有焦点环；抽屉 Tab 圈不逃逸、Escape 关闭回焦点、打开自动移焦首个导航项。
- reduced-motion：所有新动效不应用，页面自然状态全可见。

## 服务状态（交接时）
- 3000 dev：PID 62952 独立进程（cmd /c pnpm dev:web 追加日志）。
- 8000 后端：uv run uvicorn app.main:app --port 8000（日志 %TEMP%/hanzimate-api-dev.log/.err.log）。
- 8001 probe 服务器：复跑后已自然停止需求结束，当前未运行（需要时按 Phase 2 步骤重启）。
- 注意：3000/8000 曾被系统低内存清理多次，若再断按上文重启。

## 遗留 / 建议（未超出范围）
- view() 动画用 `entry 40%` 单值区间（Chromium 显式双命名区间 entry 0% entry N% 疑似解析 bug）；未来浏览器修复后可换回双值精确窗口。
- 通话页在 ≤840px 时 stackColumn 定高失效、composer 随文档流（可滚动到达），如需 pinned composer 可后续小改。
- pytest 并发时序测试偶发抖动（与前端无关）。
