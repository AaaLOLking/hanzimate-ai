# 工具开发检查点

阶段：恢复代码审查与协议验收（2026-09-17）。

已核对官方 session.update 的嵌套 function 定义、function_call_output 回传及 response.create 顺序，与现实现一致。保留原有 memory 注入和按问题展开回答策略。

本轮修复：多工具每次独立 AbortController，避免前一工具超时连带后续；只有 completed 响应可执行工具，incomplete 等终态取消；单汉字语法检索；外部调用预算用唯一事件槽事务预留，避免并发越限。

已知边界：取消/超时不保证已发出的远端 HTTP 停止计费，但结果被隔离；现有 HSK 是项目课程非官方题库；未配置工具明确 unavailable。

验证：工具后端 13 项、前端桥接 8 项、工具修改文件 Ruff 均通过。基线 92 项后端由 memory_resume 通过，最终统一检查由其负责。

lint 闭环（2026-09-17 收尾）：统一 lint 发现的 CJS require 规则问题已修复——tool-client.test.cjs 文件头按仓库惯例（参考 continuous-browser-probe.cjs）加 `/* eslint-disable @typescript-eslint/no-require-imports -- Node test runner executes this file as CommonJS. */`。复验证据：`pnpm exec eslint features/live/tool-client.test.cjs features/live/tool-client.ts features/live/tool-activity.tsx`（apps/web 下）退出码 0；`node --test apps/web/features/live/tool-client.test.cjs` 退出码 0、8 项通过；`uv run --project apps/api pytest apps/api/tests/test_tools.py -q` 退出码 0、13 项通过。本轮唯一改动即该注释行，未动 Python，故未重跑 Ruff。

真实探测：独立 Chrome SDP 请求供应商返回 403 AllocationQuota.FreeTierOnly（免费额度耗尽/仅免费模式限制），本地代理 502；尚未进入 session.updated 或工具调用。诊断会话已关闭并标 failed，无真人收音。没有重试、充值、改模型或改真实 .env。

交付记录：docs/architecture/tool-agent-validation.md 已写；.env.example 增加空 Tavily 凭证及工具预算/超时说明；UI unavailable 改为“暂不可用”兼容额度耗尽。

下一步：工具代码冻结，memory_resume 统一 lint/typecheck/build 与浏览器界面回归。真实闭环待用户处理现有 DashScope 额度后复验，不把本轮模拟测试当作真实调用通过。

冻结确认：工具侧代码冻结，可开始统一前端检查。
