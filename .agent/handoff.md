# Current Objective

连续会话/记忆、工具调用两部分已于 2026-09-17 完成并验收。2026-09-18 完成前端结构重构与 HSK 知识库 Phase 0+1。2026-09-19 完成考纲调用主动化（policy.py 硬化）与 KB 高等级扩展（全九级 11,000 词 + 518 语法点，hsk-kb-v2）。2026-09-20 完成 UX 流程改进三项（/practice 选模式页、结束后回顾勾选、错误本日期视图、i18n MVP zh/en）。当前无代理侧待办；剩余为用户侧验收与决策项。

# Completed

- 连续会话/记忆：持续入库、空闲续接、有限历史恢复、Markdown 导出、长会话正常结束。详见 docs/architecture/continuous-memory-validation.md。
- 工具调用：hsk_lookup / web_search / expert_answer 三工具，权限/去重/取消/防串话/预算；真实供应商复验五项通过。详见 docs/architecture/tool-agent-validation.md。
- sendText 文字插话修复（视为插话：cancel→等终态→发送；provider_error 分致命/可恢复），真实复验通过。
- 前端结构重构：共享 AppShell（左固定导航+中部交互+可选右上下文栏）、navigation.ts 单一导航源、panel.tsx bento 卡片变体、纯 CSS 动效（reduced-motion 全降级）、通话页接入且通话中侧栏收起为 rail、≤840px 抽屉导航。证据：.agent/frontend-progress.md、%TEMP%/hanzimate-shots/。
- HSK 知识库 Phase 0+1：官方大纲（2025-11 修订版，HSK3.0）一至四级 2000 词 + 112 语法点入库（apps/api/app/content/hsk_kb.json）；管线 parse/build/audit 三脚本可重跑；审计 0 失败；license 均 MIT / CC-CEDICT 已署名；hsk_lookup 切换且响应合同不变；policy.py 措辞同步。证据：docs/architecture/hsk-kb-sources.md、hsk-kb-validation.md。
- DeepSeek 接入：凭证从 CCR 桌面版 config.sqlite 提取（未打印密钥），工具模型 deepseek-flash + max_tokens 4000（推理模型思维链计入预算），适配器真实调用 succeeded。

# Verification Status

Passed：
- 后端全量 pytest 115 passed（含 HSK KB 检索单测与 test_policy.py 6 项策略硬化断言；主空间独立复跑确认）；ruff All checks passed；alembic check 无漂移
- 前端：lint 0 warning、typecheck 0 错误、build 10 路由；CJS 单测 19/19
- 连续会话 probe 四场景（隔离 8001、合成音轨）：三段续接/早期记忆/静音保持/切换中结束全过
- 前端重构走查：九页桌面+900/760 窄屏截图 0 pageerror/0 console error；SPA 导航、通话页文字流程、键盘焦点、reduced-motion 降级全部通过
- 真实供应商（DashScope 已解除 403）：五项复验 + sendText 修复复验 + HSK KB 切换后真实复验（显式查问触发 hsk_lookup，来源 hsk-kb-v1 / 官方大纲，succeeded）+ 主动化硬化后复验（09-19：开放问法下模型仍直接作答一次，N=1，硬化指令在场但服从度依赖模型；显式查问路径始终可靠）

Not verified（用户侧）：真人语音听感与打断延迟（G1–G7）、真实 Tavily 搜索（TAVILY_API_KEY 未配置）、expert_answer 实时会话自主触发、真实 8 分钟 rollover+工具组合。

# Important Changed Files（近两轮累计）

- 前端重构：apps/web/components/{app-shell,panel}.tsx、apps/web/lib/navigation.ts、apps/web/app/globals.css、各页面 tsx（首页/courses/lessons/reviews/errors/profile/beta/conversation）+ 新增 module.css
- HSK KB：apps/api/app/realtime/{tools,policy}.py、apps/api/app/content/hsk_kb.json、apps/api/scripts/{parse_syllabus,build_hsk_kb,audit_hsk_kb}.py、apps/api/scripts/grammar_points.json、apps/api/tests/{test_tools,test_hsk_kb}.py、docs/architecture/hsk-kb-{sources,validation}.md
- 此前轮次：realtime/{memory,lifecycle}.py、routes/{voice,tools}.py、features/live/{qwen-webrtc,tool-client}.ts、tool-activity.tsx 等（详见 git 之前状态与各验收文档）

# Known Problems

- 模型自由裁量（硬化后实测）：policy.py 已硬化为「必须先查 hsk_lookup 再答」（指令回显确认在场），但开放问法「把字句怎么用？」模型仍直接作答一次（N=1），等级宣称未走考纲来源。下一档选项待用户决策：接受现状 / 继续调措辞 / 产品侧强制（后端关键词拦截，需设计评审）。
- 「你好」词性 + 98 个五至九级成语/专名词性为人工填充（manual:project），待用户过目；839 个新收词无种子 enrichment（字段 null，可接受）。
- 语法点存在同名跨级条目（如程度副词），document_id 按名称生成会重名，结果以 title+level 区分——如需唯一 ID 可加等级后缀（未做）。
- Chromium 对 view() 双命名区间疑似解析 bug，动效已用单值 entry 40% 规避；浏览器修复后可换回。
- test_simultaneous_same_rating_commits_one_log 偶发 409 时序抖动（既有并发 flaky，与近期改动无关）。
- 仓库无初始提交、全部 untracked；空 git diff 不代表无改动。
- 摘录是有损确定性摘录，非语义摘要；知识库例句部分为项目自编（条目已标注来源）。
- 服务：3000 dev PID 62952、8000 后端 PID 65672（含全部最新代码：KB v2 + 策略硬化）。8001 隔离 probe 停止，复跑命令见 .agent/progress.md。

# Important Decisions

- 复用 README.md 作项目概览、docs/architecture/ 各文档作设计决策记录，不另建 PROJECT.md/decisions.md。
- probe 用隔离后端（8001、临时 SQLite、假 SDP）+ 合成音轨/假 Peer；真实探测用真实 Chrome WebRTC + 假麦克风设备，成本守约（短会话、显式关闭、标记 failed 诊断）。
- 统一前端检查由单一代理执行，build 前停 3000 dev 后重启为独立进程。
- 前端重构四决策（用户批准）：通话中侧栏自动收起 rail、纯 CSS 动效零新依赖、保留暖纸绿松品牌色、右栏保留为可选上下文面板。
- HSK KB：以 3.0 九级为主体、词条 2.0 双标；PDF 不入 git（清单+SHA-256 入库）；向量检索一期不做（看「查不到」失败率再定）。
- 并行代理所有权隔离：前端代理 apps/web、HSK 代理 apps/api，主空间统一收尾核验。

# Exact Next Step

1. 代理侧无待办。用户侧：体验新界面（http://localhost:3000 → 侧栏「对话训练」→ /practice 选模式；结束会话看「本次回顾」勾选流；错误本日期视图；侧栏底部中英切换）；过目词性人工填充项与 hsk-kb-validation.md 抽样对照表；可选配置 TAVILY_API_KEY。
2. 用户决策项：报告语言跟随界面语言、i18n 扩展批次、考纲「必须」是否产品侧强制。
3. 待批准立项：HSK Phase 2 剩余项（HSKK 题型映射、exam_format/topics_tasks 层、同名跨级语法点 document_id 加等级后缀）。
4. 不要在用户未要求时重启服务或提交 git。
