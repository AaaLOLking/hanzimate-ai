# HSK 知识库建设计划（立项稿）

日期：2026-09-18。状态：待用户批准后开工。策略与调研依据：[hsk-knowledge-strategy.md](./hsk-knowledge-strategy.md)（含资料清单与来源链接）。

## 1. 目标

把 `hsk_lookup` 工具的数据源从项目自编课程（12 节）升级为**官方考纲知识库**，让 agent 的等级宣称、语法答疑、练习选题全部有据可查；知识库同时服务实时语音答疑、会话报告、复习调度三条链路。

**明确不做**：刷题/押题机；真题与教材原文入库（版权）；第一期不做向量检索。

## 2. 版本锚点

以 **HSK 3.0 九级体系为主体**（2025-11 修订版大纲，2026-07-01 已全面生效），词条保留 2.0 旧等级双标（`"level": ["new-1","old-3"]`）。元数据必含 `standard`、`version`、`lastUpdated`、`sources`。

## 3. 分期计划

### Phase 0：数据获取与准备（约半天当量）

任务：
1. 下载官方资料：新版《HSK考试大纲》PDF（`https://hsk.cn-bj.ufileos.com/3.0/新版HSK考试大纲1219.pdf`）、各级大纲（chinesetest.cn 下载区）、HSKK 口试大纲 PDF（`chinesetest.cn/userfiles/file/dagang/HSK-koushi.pdf`）。存入受 Git 忽略或明确合规的 `apps/api/data/sources/`（视 license 决定是否入库，至少记录来源 URL 与下载日期）。
2. 拉取种子数据：`drkameleon/complete-hsk-vocabulary`（complete.json）与 `clem109/hsk-vocabulary`，**核查两个仓库的 LICENSE** 并记录；不允许再分发的数据只作核对参照，不直接入库。
3. 冻结 schema v0.1（词汇/语法/考试结构/话题任务四层）与本计划第 4 节一致。
4. PDF 解析工具选型：优先用本机已有 mineru-mcp 解析大纲 PDF；表格错乱时人工抽查兜底。

产出：`docs/architecture/hsk-kb-sources.md`（来源、license、下载日期、文件哈希）。

验收：文件齐备可复现；license 结论明确；schema 草案经用户确认。

### Phase 1：MVP 知识库 + hsk_lookup 切换（核心交付）

任务：
1. **管线脚本**（参考 CSCA 的 scripts 模式，放 `apps/api/scripts/` 或仓库 `scripts/`）：
   - `parse_syllabus.*`：大纲 PDF → 结构化词汇/语法草稿
   - `build_hsk_kb.*`：种子 JSON + 大纲草稿 → `hsk_kb.json`（与 `course_catalog_v2.json` 同目录同模式，版本化）
   - `audit_hsk_kb.*`：审计——种子 vs 大纲等级交叉核对、schema 校验、重复/缺漏检查、拼音词性格式校验
2. **数据范围**：HSK 1–4 级全部词汇（3.0 新大纲为准，约 2,245 词累计）+ 高频语法点约 100 个（含结构、等级、例句、来源章节）。
3. **检索层**：结构化精确检索（字/词/拼音/等级/语法点），保持毫秒级；不引入向量库。
4. **hsk_lookup 切换**：响应合同保持不变（标题/等级/版本/例句/来源标识），查不到明确返回无结果、不编造；系统提示措辞同步从「项目课程」改为「HSK 考纲知识库」。
5. **测试**：检索单测（单字/多字/拼音/等级过滤/查无此项）、响应合同测试（沿用现有断言模式）、审计脚本纳入质量检查、全量回归 + Ruff + 前端三件套。

验收（硬标准）：
- 人工抽查 50 条词条（等级、拼音、词性）与官方大纲一致率 100%；不一致项全部修复或标注存疑。
- `uv run --project apps/api pytest apps/api/tests` 全绿；`pnpm lint:web`/`typecheck:web`/`build:web` 全绿。
- 浏览器冒烟：通话中问一个 HSK2 语法问题，工具面板显示来源为考纲知识库。

### Phase 2：覆盖扩展与教学联动

- 词汇扩至 5–6 级与 7–9 级；语法点全量（572 个，3.0 口径）
- 考试结构层（HSK 笔试/HSKK 口试题型结构），HSKK 题型映射语音练习模式（听后重复/看图说话/回答问题）
- 课程 catalog ↔ 考纲语法点双向链接；会话报告错误标注等级；话题大纲喂养 scenario 选题

### Phase 3（可选，单独立项再定）

- 向量检索（应对绕弯提问）、错题本×考纲联动、学习档案等级覆盖率、实时指令「用词难度护栏」（动实时提示词，需单独验收）

## 4. Schema v0.1 草案（Phase 0 冻结）

```json
{
  "metadata": {"standard": "HSK3.0", "version": "2025-11修订版", "lastUpdated": "...", "sources": [...]},
  "vocabulary": [{"word": "把", "pinyin": "bǎ", "pos": ["prep"], "level_new": 3, "level_old": 3, "radical": "...", "frequency": 1234, "examples": [{"zh": "...", "source": "..."}], "source": "..."}],
  "grammar": [{"point": "把字句", "level": 3, "structure": "...", "examples": [...], "related_points": [...], "source": "..."}],
  "exam_format": [{"exam": "HSK3", "sections": [...], "duration_min": 0, "pass_score": 0}],
  "topics_tasks": [{"topic": "租房", "levels": [3], "tasks": [...]}]
}
```

## 5. 验证策略

- 每层数据入库前过审计脚本；抽查记录写入验收文档
- 后端：专项 pytest + 全量 + Ruff；前端：lint/typecheck/build；浏览器：语音通话冒烟
- 真实供应商复验一次（短会话，成本守约：≤2 会话 ≤1.5 分钟），确认模型在真实链路调用新 hsk_lookup 并引用考纲来源
- 验收文档：`docs/architecture/hsk-kb-validation.md`（新建，沿用既有验收文档格式）

## 6. 风险与依赖

- **版权**：大纲事实性数据（词表/语法点/题型结构）可用；教材与真题原文不入库；GitHub 种子以各自 LICENSE 为准，Phase 0 出结论
- **3.0 仍在过渡期**：官方后续可能再修订——管线必须可重跑，元数据版本字段保证可追溯
- **数据质量**：PDF 解析可能错位——审计脚本 + 人工抽查兜底，不允许「看起来对」直接入库
- **维护成本**：官方更新 = 重跑管线 + 审计 + 抽查

## 7. 分工与流程约束（沿用既有规矩）

- 主空间监控协调核验，子代理实施；共享文件先协调，统一构建由单一代理执行
- `.agent/` 检查点纪律：phase 边界必更新 progress.md；MAX_UNCHECKPOINTED_MUTATIONS=5
- 不自动 git commit、不输出密钥、不购买服务、不切换模型
- 本计划获批后开工；Phase 0/1 可由一个代理顺序完成，Phase 2 再评估是否拆分

## 8. 待用户确认的决策点

1. 数据存放：sources PDF 是否入 git（建议：来源清单入库、PDF 本体忽略，记录 URL+哈希）
2. HSKK 口语练习模式的优先级（Phase 2 里提前还是推后）
3. Phase 3 向量检索是否值得做（建议：先跑 Phase 1 看「查不到」的失败率再定）
