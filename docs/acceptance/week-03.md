# Week 3 验收清单

> 范围：实时会话状态机、Provider 安全边界、转写事件账本和可本地演示的对话 UI。

## 自动验收

- [x] 创建 VoiceSession 时生成最小 Context Pack；
- [x] 未配置 DashScope 时进入 mock 模式，并保留文本/浏览器语音降级；
- [x] 配置 DashScope 时浏览器只提交 Offer SDP，不接触 API Key；
- [x] 会话状态只能按允许路径转换，终态不能重新激活；
- [x] 转写按 `client_event_id` 幂等、按 `sequence_no` 排序；
- [x] 会话、转写与工作区查询强制按用户隔离；
- [x] 结束会话后保存时长、转写预览和工作区进度；
- [x] Web 页面展示连接、聆听、思考、说话、结束和失败状态；
- [x] 浏览器可完成一次本地模拟对话并刷新恢复转写；
- [x] 浏览器构建产物与网络响应不包含 Provider API Key。

## Provider 决策

Qwen3.5-Omni-Flash-Realtime 使用 WebRTC；Offer SDP 由浏览器生成并发给本项目后端，后端添加 DashScope Bearer Key 后向模型服务交换 Answer SDP。这样 API Key 永不进入浏览器。未配置 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_WORKSPACE_ID` 时，API 明确返回 `mode=mock`，用于开发与无密钥验收，不伪装成真实模型连接。

依据：[Qwen Omni Realtime](https://www.alibabacloud.com/help/en/model-studio/realtime)、[Realtime Token Authentication](https://www.alibabacloud.com/help/en/model-studio/realtime-token-authentication)。

## 验收证据

- API：11 个 pytest 用例通过，覆盖状态转换、幂等转写、用户隔离、mock 降级和 SDP 代理密钥保护；
- 数据库：迁移 `0001 → 0002` 与 `alembic check` 通过；
- Web：ESLint、TypeScript 与 Next.js 生产构建通过；
- 浏览器：会话创建 201、激活 200、5 条转写均 201、结束 200；刷新后恢复 5 条转写和会话时长；
- 浏览器控制台：0 error / 0 warning；
- 构建产物：未发现 `DASHSCOPE_API_KEY`；
- 截图：`output/playwright/week-03-live-conversation.png`（本地产物，不进入版本控制）。

## 尚未完成的真实 Provider Spike

当前环境没有 DashScope API Key 与 Workspace ID，因此真实 Qwen WebRTC 的建连、打断延迟、10 分钟稳定性和实际成本尚未测量。这些指标仍保留在 `docs/spikes/001-realtime-voice.md`，不能用 mock 验收结果替代。
