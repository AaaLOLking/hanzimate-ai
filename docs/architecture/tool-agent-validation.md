# 工具 Agent 实现与验收

日期：2026-09-17。当前模型保持 qwen3.5-omni-flash-realtime。

## 已实现

- 后端注册只读工具 hsk_lookup、web_search、expert_answer。模型负责发起工具意图，服务端校验工具名、参数、会话归属、连接代次和状态，保存调用结果事件。
- hsk_lookup 检索现有 course_catalog_v2.json，返回课程标题、等级、框架、版本、例句及来源标识。支持“把”等单字查询。它是小规模项目课程检索，不是官方 HSK 考纲或真题库。
- web_search 使用 Tavily，返回最多三个 HTTPS 来源及片段；expert_answer 使用现有 DeepSeek 配置，标识为未经独立核实的模型回答。缺配置时明确返回 unavailable，不伪造答案。当前仅完成适配和模拟测试。
- 前端等待 response.done completed 后执行工具，回传 function_call_output，最后一次 response.create 继续模型回答。多个调用按序处理，每次有独立超时控制器。
- 按 session / connection_epoch / response_id / call_id 去重；相同调用身份不同参数拒绝。取消、插话、新响应、断连/关闭后的迟到结果不回传模型。incomplete/failed/cancelled 响应不执行工具计划。
- 后端有超时及每会话外部调用额度，预算槽通过唯一事件键在同一事务中预留，防止并发超额。配额冲突返回 409，可由后续新调用重试；不会执行该冲突请求。
- 页面显示查询、成功、失败、不可用、取消和来源；外部额度耗尽也显示“暂不可用”。知识解释已不再固定限制为一两短句。

## 协议依据

核对了官方 [客户端事件](https://help.aliyun.com/zh/model-studio/client-events) 和 [服务端事件](https://help.aliyun.com/en/model-studio/server-events)：工具定义使用 type=function 与嵌套 function；参数完成事件包含 name、call_id、response_id、arguments；回传 conversation.item.create 的 function_call_output 后发送 response.create。原生 enable_search 与 tools 不兼容，因此未启用原生搜索。

官方通用文档目前将 conversation.item.create 描述为仅支持工具输出，而现有产品文字输入和此前 Chrome 探测使用 message/input_text；本轮在 SDP 阶段被拒绝，未重新核实文字输入支持。此差异不等于已观察到产品输入失败，需要在额度恢复后的实际 WebRTC 连接确认。

## 本轮证据

Passed:

- `uv run --project apps/api pytest apps/api/tests/test_tools.py -q`：13 项通过，覆盖来源、单字检索、授权、参数、幂等冲突、缺配置、取消/换连接/结束后迟到结果、超时、异常去敏、外部预算以及两个供应商适配器请求/结果结构。
- `node --test apps/web/features/live/tool-client.test.cjs`：8 项通过，覆盖去重、插话/新响应/关闭后的迟到结果、不完整终态、多调用回传顺序和不可用结果。
- 工具修改文件 Ruff 检查通过；整体 lint/typecheck/build 由连续会话代理统一执行，记录在其验收文档，不把专项检查当成全量结果。

真实探测受阻:

- 使用独立 Playwright Chrome、真实浏览器 RTCPeerConnection、服务端现有 DashScope SDP 代理，未读取麦克风、未连接播放元素。计划运行生产 createToolBridge 完成课程检索闭环。
- 会话 `8c849437-747c-45c0-9efd-067583fa5b47` 的 offer API 返回 502；供应商返回 403，错误码 `AllocationQuota.FreeTierOnly`，提示免费额度耗尽且仅免费模式限制。
- 拒绝发生在 SDP 交换，尚无 session.updated、工具调用或最终回答证据。不能据此推定 API key 错误或工具协议失败；没有切换模型、购买服务或修改账户计费设置。
- 诊断 Peer 和数据通道已关闭，业务会话标记 failed 并注明诊断用途，不生成真人学习记录。

## 配置和复验

HSK 检索无需新密钥。联网搜索需配置 TAVILY_API_KEY；独立问答沿用 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_DEFAULT_MODEL。参数示例已放 .env.example（空值），没有改真实 .env。默认外部工具每会话 20 次，超时 15 秒，可通过 TOOL_EXTERNAL_SESSION_LIMIT、TOOL_TIMEOUT_SECONDS 配置。

恢复真实验证需先由用户检查 DashScope 免费额度和“仅免费模式”，自行决定是否开通付费。恢复后验证：HSK 语法问题实际触发检索并引用课程；派克装备问题触发搜索，缺配置明确说明无法核实；执行时插话/结束不播报旧结果；与连续续接共同运行。当前未验收真实工具闭环、搜索质量、独立问答质量或真人语音听感。

## 边界

后端取消和超时会丢弃结果，但已发出的同步 HTTP 请求可能继续至网络超时，不能保证撤销供应商计费。工具日志保存元数据和结果；查询只保存指纹，避免复制整份聊天记录。只读工具不写长期学习记忆，确认后加入复习的闭环仍属后续范围。应用现有 demo 身份机制仍需在公开部署前接入正式认证，不将 demo header 视为生产认证方案。

## 真实复验（2026-09-17）

方法：真实供应商链路复验。Playwright 驱动产品页面（http://localhost:3000/conversation/{id}），真实 Chrome WebRTC 栈（`--use-fake-device-for-media-stream` 假麦克风，非合成 Peer 桩），后端 8000 → DashScope `qwen3.5-omni-flash-realtime`。输入走页面「文字输入」（conversation.item.create / input_text）。共 6 个诊断会话，全部显式关闭为 failed 并注明诊断用途（不生成真人学习记录）；实际实时用量约 2.7 分钟。截图证据在 %TEMP%/real-probe-*.png。

### 1. 链路 — 通过

- offer API HTTP 200（403 `AllocationQuota.FreeTierOnly` 已消失）；ICE/DTLS 由真实浏览器栈完成。
- 事件序列：out `session.update` → in `session.created` → in `session.updated`；回显 `session.tools = [hsk_lookup, web_search, expert_answer]`，`modalities=[text,audio]`，`voice=Tina`。

### 2. HSK 检索真实闭环 — 通过

会话 `45a7ffd7`（continuous 模式），文字提问「把字句怎么用？」。数据通道事件序列：

1. out `conversation.item.create`（input_text，供应商接受，无报错）
2. in `response.created` → in `response.function_call_arguments.done`（`hsk_lookup`，call_id `call_d6a4b0350da3440bb5f3e1a4`，arguments `{"query":"把字句 HSK2"}`）
3. in `response.done`（completed）→ 前端桥执行 `POST /tools/execute` → 服务端 `tool_local` 事件 `succeeded`（2 条来源：「用把字句说明事情做完了」HSK3–4、「用"比"比较两个校园选择」）
4. out `conversation.item.create`（function_call_output，status=succeeded）→ out `response.create`
5. 最终回答（已持久化转写）：「'把'字句一般用来表示你做了某事…结构：'把 + 东西 + 动词 + 结果 + 了'…例子：'我把作业写完了。' '请把门关上。'」——结构与例句与课程 `用把字句说明事情做完了` 的 explanation/examples 一致，回答确实基于检索内容。

页面工具活动区显示「中文学习资料 · 已返回 · 查看资料来源（2）」。观察项：模型口播未念出课程名称（系统提示要求说明引用资料名称）；来源在面板与服务端事件中完整。另观察到供应商行为怪癖：下一轮模型曾以完全相同 call_id+arguments 重发 `hsk_lookup`，被桥接层 seen 去重正确忽略。

### 3. 缺配置路径 — 通过（附观察）

会话 `47231d17`。提问「英雄联盟派克这个英雄现在怎么出装？」→ `web_search`（call_id `call_56e3b3d4db534ca781198313`，query「英雄联盟 派克 出装 版本 2024」）→ 服务端 `tool_external` 事件 `unavailable` + `tool_budget_reserved` → function_call_output(unavailable) → response.create → 最终回答原文开头：「联网搜索暂时不可用，无法核实最新出装。」——明确 unavailable，未伪造来源。面板显示「联网搜索 · 暂不可用」。`GET /tools` 确认 `web_search`/`expert_answer` available=false。

观察（不算失败，原样记录）：声明不可用后，模型仍基于记忆给出装备建议（「派克一般出'三相之力'…」），用了「一般」「具体要看对局情况」等弱化措辞，未伪装成检索结果；但与系统提示「不可用时不编造装备、来源或答案」的字面要求有张力，留给产品侧决定是否加约束。

### 4. 插话/取消 — 通过

会话 `efd70a97`。浏览器侧将首个 `/tools/execute` 延迟 6 秒制造执行窗口；工具在途时发送第二条用户文字（产品 sendText → 桥 `cancel()`：代次递增 + `POST /tools/cancel` + abort）。

- 数据通道层面：第二条用户消息之后，outgoing 仅有 `conversation.item.create`（用户消息）+ `response.create`；旧 call_id 的 `function_call_output` 泄露数为 0。
- 服务端：延迟请求到达时命中 `tool_cancelled` 事件，原样返回 `{"status":"cancelled","message":"本轮已取消。"}`，工具未执行；`tool_cancelled`（response_id `resp_U9waBgS4NGvlDTh6QB46O`）已记录。面板显示「工具查询 · 已取消 / 查询已取消，旧结果不会继续播报。」
- 「结束会话」变体与插话共用同一 `cancel()` 栅栏（单测覆盖），为避免生成 completed 学习记录未单独实跑。

### 5. continuous 共存 — 通过（按清单口径）

页面所有会话均为 `continuous: true`（探测会话已核实）；continuous 模式下 `session.updated` 回显确认工具定义被接受，且上述 hsk_lookup 成功即发生在 continuous 会话内。真实 8 分钟 rollover 与工具的组合按约定未测（成本）。

### 新发现：真实供应商语义暴露的产品问题（未改代码，原样记录）

会话 `894bff18`：在模型回答仍进行中（无 `response.done`）时发送 `conversation.item.create`（input_text），供应商返回 `error` 事件，消息原文「Conversation already has an active response」。产品 `sendText` 无空闲守卫，且 `provider_error` 处理会把整个会话降级为文字模式（该会话已记录 `provider_error` + `fallback_activated` 事件）。含义：真实用户在 AI 说话时打字发送，会触发供应商错误并丢掉实时语音通道。此前的模拟/降级路径无法暴露该语义，需产品侧决策修复（例如发送前取消在途 response 或禁用输入直至 response.done）。

### 仍未能验收

- `expert_answer` 真实不可用路径（模型未被触发；与 web_search 对称，仅单测覆盖）。
- 结束会话在执行途中的独立实跑（同一代码路径，见第 4 条）。
- 真实 8 分钟 rollover + 工具组合；真人语音听感；真实联网搜索质量（TAVILY_API_KEY 未配置）。

### 环境与善后

- 复验期间 3000 dev server（原 PID 65972）发生 Jest worker 崩溃、全路由 500，已重启；当前实例由验收代理在后台启动，日志 %TEMP%/hanzimate-web-dev.log。8000 后端未动。
- 6 个探测会话（33e01c23 / 48ece59b / 45a7ffd7 / 47231d17 / 894bff18 / efd70a97）全部 status=failed 并注明诊断用途；Peer/数据通道随浏览器关闭断开；未产生真人学习记录。

### 修复与复验（2026-09-17 晚，同日）

修复策略（用户已定）：AI 回答进行中用户发文字 = 视为插话——先取消在途回答，等供应商确认终态后再发新消息；provider_error 按作用域分类，可恢复的单响应错误不再把整个会话降级为文字模式。

代码改动（仅前端，后端未动）：

- `apps/web/features/live/qwen-webrtc.ts`：传输层跟踪在途 response（`response.created` 置位，`response.done/cancelled/failed` 清位并释放等待者）；新增 `sendTextInterject(text, terminalTimeoutMs=3000)`——有在途 response 时先发 `response.cancel`，等待该 response 的终态事件（3 秒兜底超时）后再发 `conversation.item.create` + `response.create`；`close()` 释放全部等待者，挂起的插话以通道不可用错误拒绝而不是挂死。空闲时调用等价于原 `sendText`。
- `apps/web/app/conversation/[workspaceId]/page.tsx`：`sendText` 在 WebRTC 模式且 provider 有在途 response 时（`providerResponseActiveRef`，由 `response_started`/`response_terminal` 维护）走插话分支——把当前回答标记 interrupted（静音本地播放、`updatePlayback(interrupted)`、记录 `interruption` 事件 reason=`text_barge_in`），再 `await sendTextInterject`；无在途 response 时保持原 `sendText` + `requestResponse` 路径不变。`provider_error` 处理改为分类：致命错误（认证/权限/quota/计费级，见 `isFatalProviderError` 的 auth|permission|forbidden|unauthori|api_key|access_token|quota|billing|insufficient 判据）才 `activateTextFallback`；可恢复错误只记录事件（payload 带 code/error_type/classification）并提示用户，语音通道保留。
- `apps/web/features/live/provider-events.ts`：`provider_error` 事件解析增加 `code`/`errorType` 提取；新增导出 `isFatalProviderError`。

测试：`node --test apps/web/features/live/*.test.cjs` 共 19 项通过——原有 tool-client 8 项（插话/新响应/关闭后零旧结果泄露等行为不变）+ 新增 qwen-webrtc 6 项（无在途 response 直接发送；插话先发 cancel、终态后发送；`response.cancelled` 事件释放等待；终态等待超时兜底；close 拒绝挂起插话；原 `sendText` 语义不变）+ 新增 provider-events 5 项（error 事件字段解析；active-response 冲突可恢复；auth/quota/key 致命；未知与限流默认可恢复）。统一检查：后端 pytest 94 passed、Ruff All checks passed；`pnpm lint:web` 0 warning；`pnpm typecheck:web` 0 错误；`pnpm build:web` 成功（10 路由）。

真实复验（成本守约：2 个短会话，单会话墙钟 30–40 秒、供应商通道内约 5–8 秒，合计远低于 1.5 分钟上限）：方法同前（真实 Chrome WebRTC + 假麦克风，Playwright 驱动产品页面），probe 脚本 %TEMP%/real-probe-4-text-interject.cjs，在开场回答仍在流式输出（`response.created` 已到达、无 `response.done`）时经页面「文字输入」发送文字。两个会话（`d794fb4f`、`4b63b8c6`）事件序列一致，第二次运行全部断言 `passed:true`：

1. out `response.cancel`（第二个会话 t≈3.6s，紧随用户发送）→ 供应商仍以 `response.audio_transcript.delta` 冲刷完已缓冲的口播 → in `response.done`（status=`cancelled`）确认终态 → out `conversation.item.create`（input_text）→ out `response.create`。供应商在 cancel 后继续冲刷缓冲音频的行为证实「等待终态再发送」是必要的——若在 cancel 后立即发送会再次撞上 active response 冲突。
2. 全程无 in `error` 事件（修复前会话 894bff18 在此场景收到「Conversation already has an active response」）。
3. 服务端事件无 `provider_error`、无 `fallback_activated`；记录 `interruption`（reason=`text_barge_in`）1 次；页面保持语音模式（providerBadge 仍为 `Qwen WebRTC · qwen3.5-omni-flash-realtime`，无降级横幅）。
4. 文字回答正常返回并持久化（第二会话回答「别担心，休息一下明天就会充满能量。」）；被插话打断的开场回答转写 playback_status=`interrupted`，用户文字 source=`browser_text` final。
5. 两个会话均显式 PATCH status=failed 注明诊断用途，未产生真人学习记录；截图证据 %TEMP%/real-probe-4-text-interject.png。

遗留：可恢复 provider_error 目前仅提示并保留连接，不做自动重试（active-response 冲突已由插话栅栏根除，剩余场景未见实例）；`expert_answer` 真实路径与 8 分钟 rollover + 工具组合仍按本节「仍未能验收」口径未测；真人语音听感仍需用户本人验收。

### expert_answer 适配器真实验证（2026-09-18，主空间）

用户授权从本机 CCR 桌面版配置（`AppData/Roaming/claude-code-router/config.sqlite` 的 deepseek provider）提取凭证写入根 `.env`（DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_DEFAULT_MODEL，提取与写入全程未打印密钥值）。

适配器实测发现：`deepseek-flash` 与项目原默认 `deepseek-v4-flash` 均为推理模型，`max_tokens=1000` 会被思维链（reasoning_content）耗尽导致 `content` 为空、`finish_reason=length`——项目原默认配置存在潜在空回答缺陷。（课程导师/会话总结两个 DeepSeek 路径此前已显式 `thinking: disabled`，不受影响；只有工具适配器没关思考。）

中间曾短暂用 `deepseek-chat`（非推理直出，119 tokens）验证链路；随后用户决策改用 v4 系推理模型并提高预算。`/models` 端点探测：该 key 实有 `deepseek-flash` 与 `deepseek-v4-pro` 两个模型；`deepseek-v4.1-flash`/`deepseek-v4.1` 均 HTTP 400 不存在；`deepseek-v4-flash` 被接受但回显 `deepseek-flash`（只是别名）。最终定稿（用户选择快速推理线，语音对话中低延迟优先）：`DEEPSEEK_DEFAULT_MODEL=deepseek-flash`，`tools.py` 的 `max_tokens` 1000→4000（代码注释注明原因），后端重启后 `execute_tool("expert_answer", …)` 真实调用 `status=succeeded`、回显 `model=deepseek-flash`、回答结构正确（把/被字句对比 + 例句）、事件带 `evidence_kind=unverified_model_answer`。如需更深推理质量，`.env` 改 `deepseek-v4-pro` 即可切换（同一 key 支持）。

测试同步：`test_tools.py` 载荷断言更新为 4000；`test_courses.py`/`test_learning_memory.py` 两个合同测试在 Settings 构造中显式钉住 `deepseek-v4-flash`，消除对本地 .env 的隐式依赖。全量 pytest 94 passed、Ruff 通过。

仍未测：实时会话中模型自主触发 expert_answer 的端到端路径（可在真人语音体验中观察）。

### HSK 知识库切换后真实复验（2026-09-18 晚，主空间）

背景：`hsk_lookup` 数据源已从项目课程切换为官方考纲知识库（`hsk_kb.json`，版本 `hsk-kb-v1`），用真实供应商链路复验（方法同「真实复验」节：真实 Chrome WebRTC + 假麦克风 + 页面文字输入；runner `%TEMP%/hanzimate-real-runner.cjs`，脚本 `%TEMP%/real-probe-5-hsk-kb.cjs`）。

结果：**通过**。显式提问「帮我查一下考纲：把字句在 HSK 里是几级？结构是什么？」→ 模型发起 `hsk_lookup` → 服务端 `succeeded` → `function_call_output` 回传 → 回答继续。工具输出首个来源：title=把字句、version=`hsk-kb-v1`、kind=grammar、level=HSK3（亦见HSK4）、framework=HSK3.0（2025-11修订版）、rights=官方大纲语法点（例句来自项目课程 course:campus-chinese-foundations/ba-result-complement）。`session.update` 回显三工具注册；instructions 含考纲知识库新措辞（覆盖范围声明、来源引用要求）；`/tools` 可用性 hsk_lookup=true、expert_answer=true、web_search=false（未配置，预期）。页面零错误；会话已标 failed 诊断用途，无学习记录。

**观察（产品决策点）**：同一语法点的开放问法「把字句怎么用？」在另一会话中模型**直接作答而未调用工具**（回答内容正确但未引用考纲来源）——工具调用是模型自由裁量，instructions 目前措辞为「优先调用」。是否硬化为「HSK 语法问题必须调用 hsk_lookup」待产品决策。

探测脚本自身修复（非产品代码）：开场白被取消后的迟到 `response.done` 会与新回合事件交错，探测等待需按发送时刻基线锚定，否则会误读为「未触发」。

### 主动化硬化与高等级扩展后真实复验（2026-09-19，主空间）

政策硬化（policy.py）：「凡涉及 HSK 语法/词汇/等级的问题必须先调用 hsk_lookup 再作答，即使自认知道答案；教学引入语法点先查等级再讲；寒暄与无关问题豁免」（证据：`test_policy.py` 6 项）。KB 已扩至 11,000 词（全九级，7–9 为等级带）+ 518 语法点（`hsk-kb-v2`）；pytest 115 passed、ruff 绿、审计 0 失败。

真实探测（开放问法「把字句怎么用？」，1 个会话约 1 分钟，会话已标 failed 诊断）：session.update 回显确认硬化指令已在场——**但模型仍直接作答未调工具**，回答内容正确（结构与把字句相符），然而等级宣称「HSK3 级」未走考纲来源，违反了「等级宣称必须有来源」的指令。结论：措辞硬化只能提高概率，不能强制——该模型（qwen3.5-omni-flash-realtime）在 N=1 样本下未服从「必须」。显式查问路径（「帮我查一下考纲…」）始终可靠（前一日已验证）。

可选下一档（待用户决策）：a) 接受现状——显式查问可靠、面板来源可见；b) 继续迭代措辞（边际收益递减）；c) 产品侧强制——后端检测 HSK 关键词回合且无工具调用时注入提示（需设计评审，影响面大）。
