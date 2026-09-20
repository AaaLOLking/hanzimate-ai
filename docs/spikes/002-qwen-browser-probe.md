# Qwen 浏览器协议探测（2026-09-16）

环境：Windows 10/11，Chrome 153.0.8010.47，本地 FastAPI SDP 代理，模型 `qwen3.5-omni-flash-realtime`，音色 Tina。

## 方法和边界

使用 Playwright CLI 在浏览器中建立 RTCPeerConnection，调用现有会话创建和 offer API，发送服务端生成的 session.update。音频 transceiver 为 sendrecv，但没有采集麦克风，也没有连接音频播放元素。两次诊断连接均已关闭，对应业务会话已标记 failed 并注明诊断用途，不产生学习者转写或学习报告。

这是浏览器中的真实供应商协议探测，不是完整产品界面或真人语音验收。前一轮 aiortc 数据通道等待超时不能据此归因于凭证或网络；本轮 Chrome 连接成功，aiortc 超时原因尚未确定。

## 实测证据

- SDP 代理返回 HTTP 200，浏览器接受 answer。
- ICE candidate pair 为 succeeded，DTLS 为 connected，浏览器发起的 `oai-events` 通道为 open。
- Qwen 另建 `txt` 通道回传事件；需要在协商前监听 `datachannel`。项目现有适配器已实现此行为。
- 第二次探测自创建 Peer 起 2291 ms 收到 session.created，2381 ms 收到 session.updated；时间包含人为等待 ICE 收集的 1800 ms，不是模型响应延迟。
- 初始确认的 turn_detection 为 semantic_vad，silence_duration_ms 为 1400。
- 发送“请只用中文说：你好，欢迎练习中文。”后，返回 conversation.item.created、response.created、response.audio_transcript.delta、response.audio_transcript.done、response.audio.done 和 response.done。
- 入站音频统计为 196 个包、139632 字节。未连接播放元素，未验证可听性或声学停止时间；totalAudioEnergy 为 0，不能据此声称播放成功。
- 热更新 silence_duration_ms 为 900 后，session.updated 回显该设置。
- 第二轮请求较长故事，收到 response.created 后计划延迟 300 ms 发送 response.cancel；最终 response.done.status 为 cancelled。期间仍有字幕到达。response.created 到 cancelled 为 1263 ms；没有记录取消实际发送时间和停止播放时间，不能推算精确打断延迟。
- 第二轮 response.done 未提供本次采集路径下的 response.usage；用量保持 unknown。

## G1–G7 状态

| 项目 | 本轮结论 | 仍待验证 |
|---|---|---|
| G1 | SDP、ICE、DTLS、两个数据通道、配置确认通过单次探测 | 产品界面、真实麦克风与可听输出、成功率 |
| G2 | AI 字幕 delta/done 真实返回 | 学习者语音预览及最终转写、端到端持久化 |
| G3 | semantic_vad 配置被接受 | 附和音误打断、真实插话、自我修正 |
| G4 | 手动取消得到 cancelled 终态 | 取消后音频尾巴、实际停止播放、自动打断 |
| G5 | 停顿参数热更新得到确认 | 语速和教学指令的实际行为 |
| G6 | 未验收 | 浏览器断网、重连及真实错误分类 |
| G7 | unknown | 原始用量字段和账单核对 |

全局能力声明继续保留 unverified；上述小样本证据不等于 G1–G7 整体通过。
