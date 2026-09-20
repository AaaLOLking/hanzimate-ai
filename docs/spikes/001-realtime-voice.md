# Spike 001：Qwen 实时语音

## 目的

验证浏览器到 Qwen Realtime 的 WebRTC 链路能否满足中文学习对话的延迟、打断、转写和成本要求。

## 不验证

- 专业发音评分；
- 长期记忆准确性；
- 8 分钟以上的单 Provider 会话；
- 正式并发容量。

## 当前进度（2026-08-24）

- 已完成浏览器 WebRTC 客户端、后端 SDP 代理、状态 UI、转写与可靠性事件账本和 mock 降级；
- 已实现两次自动重连、最近 6 轮恢复上下文、60 秒预算预警和文字/本地朗读降级；
- 已验证 API Key 不出现在客户端配置、网络响应和前端构建产物；
- 官方 WebRTC 鉴权不是浏览器短时凭证模式，而是在 SDP HTTP 交换时携带 Bearer Key；本项目由后端代理该交换；
- 当前环境没有 DashScope API Key / Workspace ID，真实建连、VAD、打断、延迟与成本数据仍未执行。

官方依据：[Qwen Omni Realtime](https://www.alibabacloud.com/help/en/model-studio/realtime)、[Token Authentication](https://www.alibabacloud.com/help/en/model-studio/realtime-token-authentication)。

## 前置条件

- 百炼测试 Workspace 与服务端 API Key；
- qwen3.5-omni-flash-realtime 可用；
- Chrome、Edge 和 Safari 各一台测试设备；
- 3 段外国学习者中文测试音频；
- 不记录真实个人身份信息。

## 场景

1. 正常三轮点餐对话；
2. 用户在 AI 输出 500–1500 ms 后插话；
3. 用户只说“嗯”“啊”而不应触发语义打断；
4. 用户说“慢一点”后调整语速；
5. 5 分钟时生成滚动摘要并裁剪旧上下文；
6. 短暂断网后恢复或明确降级。

## 必须记录

每轮记录：

- session_id、turn_id；
- connected_at、speech_started_at、speech_stopped_at；
- response_created_at、first_audio_at、response_done_at；
- interruption_requested_at、audio_stopped_at；
- input/output audio seconds；
- input/output Token；
- estimated_cost_cny；
- model snapshot；
- connection and provider error code。

## 计算

- response_latency_ms = first_audio_at - speech_stopped_at；
- interruption_latency_ms = audio_stopped_at - interruption_requested_at；
- effective_speaking_ratio = user_speech_seconds / session_seconds；
- cost_per_effective_minute = total_cost / user_speech_minutes。

## 通过标准

- 8 分钟会话完成且转写未丢失已完成轮次；
- WebRTC 建连成功率至少 98%；
- response latency：P50 ≤ 1200 ms，P95 ≤ 2500 ms；
- interruption latency：P95 ≤ 500 ms；
- “嗯/啊”误打断率低于 10%；
- 能得到真实成本数据；
- 浏览器不接触长期 API Key，SDP 鉴权交换由后端代理。

## 失败决策

- 延迟失败：测试 Qwen Audio Realtime 或 ASR → LLM → TTS 级联；
- 打断失败：保留 push-to-talk 降级；
- 成本失败：缩短上下文、提高摘要频率或限制每日分钟；
- 转写失败：允许用户编辑转写，低置信度不进入错误记忆。
