# 当前外部阻塞

## Live v1 真实 Qwen 验收

状态：凭证、Chrome WebRTC 连接、配置确认、AI 字幕和入站音频包已通过真实探测；真人语音体验仍待验收（2026-09-16）。

已将模板中的 DashScope 凭证转入受 Git 忽略的本地 `.env`，并清空模板对应值。后端可读取两项配置。使用 aiortc 生成真实 SDP，经现有 Qwen Provider 完成信令交换并解析应答，但等待数据通道开启 20 秒超时。该探测没有采集麦克风，也未完成真实语音交互，不能替代浏览器 G1–G7 验收。

后续浏览器探测已确认 ICE/DTLS 连通、语义 VAD 配置确认、AI 字幕、入站音频包、停顿参数热更新和取消终态。详见 [实测记录](docs/spikes/002-qwen-browser-probe.md)。aiortc 超时原因仍未确定，不再将其当作浏览器链路阻断。

下一步：使用麦克风与耳机完成用户转写、真实语义插话、音频尾巴和听感验收；补充断网恢复、真实延迟分布与用量。凭证不能写入版本控制或测试输出。

## 工具真实供应商验收（DashScope 额度）

状态：已解除（2026-09-17）。用户处理额度后真实链路复验通过：offer 200、session.updated 回显三个工具、HSK 检索真实闭环（检索→回传→回答引用课程一致）、缺配置明确 unavailable、插话/取消零旧结果泄露、continuous 共存通过。详见 [工具验收记录](docs/architecture/tool-agent-validation.md)「真实复验（2026-09-17）」节。实际实时用量约 2.7 分钟，6 个诊断会话全部标记 failed 善后。

剩余未验收：expert_answer 真实触发（模型未调用，与 web_search 对称、单测覆盖）；真实 8 分钟 rollover + 工具组合；真实搜索质量（需配置 TAVILY_API_KEY）。复验另暴露一个产品缺陷（AI 回答进行中发文字被供应商拒绝、sendText 无空闲守卫），修复方式待用户决策，详见 .agent/progress.md。
