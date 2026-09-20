# 前端结构重构计划（立项稿）

日期：2026-09-18。状态：待用户批准后开工。

## 1. 背景与目标

用户要求重构前端结构：左侧固定导航（各可选项）+ 中部交互区域，板块设计参考苹果式流畅滑动风格（bento 网格 / 玻璃拟态 / 平滑动效）。

**技术事实澄清**：现有前端已是 React（Next.js 16.3.1 + React 19.2.8），本计划不是换框架，而是在 Next.js 内做**布局结构统一 + 视觉/动效升级**。

## 2. 现状盘点（代码实测）

- **已有约定**：`globals.css`（3729 行）已有设计 token（`--ink/--paper/--green/--amber/--sidebar` 暖纸绿松色系）、`.appShell` 三列网格（264px 侧栏 + 中部 minmax(640px,1fr) + 344px 右栏）、`.sidebar/.navItem/.navIcon/.navBadge` 样式、skipLink、`prefers-reduced-motion` 降级支持
- **问题**：appShell 只是 CSS 类，不是共享组件——首页自己硬编码 `navigation` 数组，各页面布局各自为政；没有统一的 React 层 AppShell
- **零依赖**：`package.json` 只有 next/react/react-dom，无 Tailwind、无动画库——本仓库偏好极简依赖
- **约束**：`apps/web/AGENTS.md` 警告此 Next.js 版本与训练知识有破坏性差异——实施代理写代码前必须查 `node_modules/next/dist/docs/`
- 页面清单：首页（仪表盘）、conversation/[workspaceId]（聚焦通话）、courses、lessons/[id]、reviews、errors、profile、beta、onboarding

## 3. 目标结构

```
┌──────────────────────────────────────────────┐
│ 左侧固定侧栏（AppShell 共享组件）  │  中部交互区（各页面内容）  │
│  · 今日（首页仪表盘）              │                          │
│  · 对话训练                        │   bento 卡片式板块，       │
│  · 系统课程                        │   平滑滚动/入场/悬浮动效    │
│  · 今日复习                        │                          │
│  · 错误本                          │                          │
│  · 学习档案                        │                          │
│  · 体验反馈                        │                          │
└──────────────────────────────────────────────┘
```

- **共享 `<AppShell>` React 组件**（`apps/web/components/` 或 `app/` 布局组）：统一侧栏导航（单一数据源）、激活态、中部内容插槽；右侧 344px 栏保留为可选上下文面板
- **bento 卡片组件**（Panel/Card 变体）+ 玻璃拟态质感（`backdrop-filter` 磨砂，克制使用）
- **平滑动效**：入场渐入、板块悬浮、页面间过渡、滚动驱动动画（scroll-driven animations）；全部服从 `prefers-reduced-motion`
- **通话页特殊处理**：通话激活时侧栏自动收起为细条（保持聚焦通话设计），结束后恢复

## 4. 设计参考（调研结论）

苹果式流畅感的主要来源（已调研）：
- **Bento 网格**：Apple 在 Keynote/iOS 推广的多入口卡片网格（[LinkedIn 分析](https://www.linkedin.com/pulse/bento-boxes-arent-just-lunch-theyre-game-changer-ui-design-singhal-mzb7c)、[2025/26 趋势](https://firmencharisma.de/webdesign-trends/)）
- **玻璃拟态/Liquid Glass**：`backdrop-filter: blur()` + 半透明（Apple macOS/iOS 26 风格）
- **滚动驱动动画**：现代浏览器原生 CSS `animation-timeline: scroll/view()`，零依赖即可实现苹果式板块滑动
- 参考模板：[Versekit bento grid](https://versekit.io/template/bento-grid)、[纯 CSS 布局片段集](https://www.webdevpuneet.com/2026/08/10-copy-paste-layout-snippets-that.html)（app shell、bento、sticky sidebar、snap scroll）

## 5. 分期

### Phase 1：结构统一（核心交付）
- 新建 `<AppShell>` 共享组件 + 统一导航配置；各页面逐个迁移（首页、课程、复习、错误本、档案、反馈）
- 整理 globals.css：token 分层（色板/阴影/圆角/动效时长），Panel 卡片组件化
- 验收：`pnpm lint:web`/`typecheck:web`/`build:web` 全绿；Playwright 逐页截图核对导航一致、无样式坍塌

### Phase 2：动效与通话页适配
- bento 板块入场/悬浮/滚动驱动动效（纯 CSS 优先）；页面过渡
- 通话页接入 AppShell + 通话中侧栏自动收起
- 验收：既有浏览器流程测试不破（含 probe 四场景复跑）；reduced-motion 下动效全关

### Phase 3：打磨
- 响应式（窄屏侧栏收为抽屉）、键盘导航与焦点管理复查
- 视觉走查清单 + 浏览器全流程回归

## 6. 流程约束（沿用老规矩）

- 主空间协调核验，子代理实施；统一构建单执行者；`.agent/` 检查点纪律
- 不改后端 API 合同；不动功能逻辑，纯结构/视觉层
- 实施代理先读 `node_modules/next/dist/docs/` 相关指南再写代码
- 无新依赖为默认；任何新增依赖需单独说服

## 7. 待用户确认的决策点

1. **通话页侧栏**：通话中自动收起为细条（推荐，保持聚焦设计）/ 常驻 / 通话页不进 AppShell
2. **动效技术路线**：纯 CSS 滚动驱动动画（推荐，零新依赖）/ 引入 motion 库（能力更强但破零依赖传统）
3. **色彩方向**：保留现有暖纸+绿松品牌色、只做结构与动效升级（推荐）/ 转向更苹果的纯白冷调
4. **右侧 344px 上下文栏**：保留为可选面板（推荐）/ 取消并入中部
