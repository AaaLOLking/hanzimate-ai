# Spike 002：DeepSeek 结构化错误提取

## 目的

验证 deepseek-v4-flash 能否从中文学习证据中稳定返回可校验、低误报的候选错误。

## 当前实现（2026-08-24）

- 已实现 DeepSeek OpenAI 兼容的 `/chat/completions` 服务端适配器；
- 使用 `deepseek-v4-flash` 非思考模式与 JSON Output，持久化前强制通过 Pydantic 合同；
- Prompt 明确包含 json、完整输出示例、最多 3 个错误、ASR 不等于发音证据等边界；
- 空内容只重试 1 次，HTTP、超时或非法结构返回 502，不把失败内容写入长期记忆；
- 模型生成字段在服务端归一化为 `candidate`，并覆盖 session、model、Skill 版本；
- 无密钥环境使用 `local / rule-summary-v1`，只覆盖 3 个确定性中文错误模式，不能作为 DeepSeek 精度证据。

官方接口依据：[DeepSeek V4.0 发布说明](https://api-docs.deepseek.com/news/news260424/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode)、[Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion/)。当前环境没有 DeepSeek 凭证，因此尚未执行 20 个种子案例的真实模型质量评测。

## 固定输入

- learner profile；
- current task；
- utterance transcript；
- ASR 置信度；
- existing error cluster keys；
- model 和 Skill 版本。

## 固定输出

- packages/chinese-learning-coach/schemas/error-event.schema.json；
- packages/chinese-learning-coach/schemas/session-summary.schema.json。

## 数据集

首轮使用 evals/gold-errors.jsonl 的 20 个种子案例。扩展到 100 个前，至少覆盖：

- 正确但非母语风格的表达；
- 同一句因意图不同而有不同修改；
- ASR 模糊；
- 量词、语序、体标记、把字句、语用；
- 不应从文本判断的发音问题。

## 实验变量

- 非思考与思考模式；
- temperature 或等价采样设置；
- 单条与批量输入；
- 是否提供现有 canonical keys；
- 同一案例重复 5 次。

## 指标

- JSON Schema pass rate；
- error precision；
- error recall；
- acceptable-variant false-positive rate；
- taxonomy exact match；
- canonical-key consistency；
- explanation level fit；
- average latency and cost。

## 通过标准

- 自动修复前 Schema 通过率 ≥ 98%，修复后 ≥ 99.5%；
- 高价值错误 precision ≥ 90%；
- 正确表达误报率 < 5%；
- 低置信度 ASR 不生成 confirmed；
- 同一输入五次的 type/subtype 一致率 ≥ 90%；
- 单会话最多返回 3 个重点。

## 写入边界

模型只能返回 candidate。用户确认或高可信确定性规则之后，应用才创建 confirmed 状态和复习卡。
