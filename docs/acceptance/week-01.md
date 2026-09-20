# Week 1 验收清单

## 产品

- [x] PRD 明确目标用户、范围和五条核心用户故事
- [x] 信息架构定义桌面三栏、响应式行为和页面状态
- [x] ERD 区分证据事件、长期错误、复习卡和课程版本
- [ ] 由产品负责人确认八项默认假设

## Skill

- [x] 使用标准初始化器创建 chinese-learning-coach
- [x] SKILL.md 无模板 TODO
- [x] Error、Lesson、Summary、Profile Schema 可解析
- [x] 至少 20 个错误评测种子案例
- [x] quick_validate.py 通过
- [x] 自带资源校验脚本通过

## 工程

- [x] pnpm install 成功
- [x] Web lint 与 build 通过
- [x] API pytest 与 Ruff 通过
- [x] /healthz 返回 ok
- [x] 首页显示 Codex 风格三栏基线
- [x] .env.example 不包含真实密钥

## 技术 Spike 准入

- [x] realtime-voice：先定义延迟、打断和成本记录格式
- [x] error-extraction：先冻结 JSON Schema 与金标准
- [x] memory-retrieval：先冻结 namespace 和用户隔离规则
