# HSK 知识库建设进度（Phase 0 + Phase 1 + Phase 2 高等级扩展）

代理：HSK 知识库建设代理。开始时间：2026-09-18；Phase 2 完成：2026-09-19。
**状态：Phase 0 + Phase 1 + Phase 2（词汇 5–9 级 + 语法全量）已完成，待主空间收尾验收。**
并行约束：apps/web/** 归前端重构代理，本代理未触碰；policy.py 归另一代理（本代理未触碰，
其措辞硬化保持原样）；未 git commit；未重启服务；未做浏览器/真实供应商复验（按约定主空间统一收尾）。

## 阶段：Phase 2（高等级扩展）完成内容

**词汇扩展（官方 PDF 第 130–354 页）**
- 词表从 2000 扩至 **11000**：L1=300 / L2=200 / L3=500 / L4=1000 / L5=1600 / L6=1800 /
  七—九级带=5600（序号 5401–11000，末行 11000 为词表实际结束，页 355 起为汉字大纲）。
- 解析器沿用坐标行聚类 + 序号连续性自检；新增 `拟声` 词性（哈/哇/轰 3 行）；
  等级标签接受裸 `7-9`（等级带）。
- 官方空词性格 473 行（L5–9）：种子填充 375、人工填充 98（成语为主，见 build_hsk_kb.py
  MANUAL_POS，含 中华民族/糖尿病/多年来=名，打下手/掏腰包/捉迷藏=动）。

**语法点扩展（官方 PDF 第 386–406 页，HSK（一级）…（七—九级）语法）**
- grammar_points.json 从 112 → **518 条**（L1=56/L2=65/L3=85/L4=86/L5=64/L6=34/L7带=128）。
- 语法表改用 find_tables 单元格几何提取（每表按表头单元格定列边界——各页列 x 不同；
  水印按字号 >20pt 剔除；除页脚/章节标题外全部字符须被单元格覆盖，否则解析失败）；
  结构化细目 312 条，复句/固定格式/固定短语按行拆分为独立语法点。
- 112 条 Phase 1 精选全部保留（名称/例句/related 不动，provenance.reused_curated 标注）；
  406 条新点逐条配项目自编例句（含拼音），example_source=project-authored。
- audit 对 1–4 级语法同时对照「行文本草稿（Phase 1 独立提取）∪ 结构化提取」两个来源校验。

**检索层适配（tools.py）**
- KB_VERSION = hsk-kb-v2；LEVEL_WORDS 加 七/八/九；query_level_filter 接受 HSK1–9 与一—九级。
- 等级带语义：BAND_LEVELS={7,8,9}，level_hit_filter 使 HSK7/8/9 与七/八/九级查询命中
  level_new=7 的全部条目；条目等级显示 HSK7-9；词性/类别精确匹配加分（「HSK9 成语」类查询）。
- TOOL_DESCRIPTIONS 与 no_results/succeeded 措辞更新为一至六级 + 七至九级等级带 + 全量语法点。

**7–9 级带 schema 决策（向后兼容，已写入 hsk-kb-sources.md 与 KB metadata.band_note）**
- 官方结构：3.0 中七至九级为一个等级带，词表等级列直接印「7-9」，语法大纲为
  「HSK（七—九级）语法」一章。入库：`level_new` 保持 int=7，新增可选字段
  `level_band="7-9"`，`level_note="（7-9）"`（与 1–4 级交叉注记同格式）；检索层映射见上。

## 验证证据（终验命令 + 退出码，2026-09-19）
- parse_syllabus.py → exit 0（11000 行，序号 1–11000 连续断言通过）
- build_hsk_kb.py → exit 0（11000 词 + 518 语法点）
- audit_hsk_kb.py → exit 0，结论 `OK: 11000 vocab, 518 grammar points, 0 failures`
  （种子交叉核对 10087 一致 / 65 不一致仅报告 / 839 不在种子）
- `uv run --project apps/api pytest apps/api/tests` → **115 passed**（27s 全绿；
  test_review_migration 并发 flaky 本轮通过，Phase 1 已记录其为既有竞态）
- `uv run --project apps/api ruff check apps/api` → All checks passed
- 抽样对照表：docs/architecture/hsk-kb-validation.md（50 词含 7-9 带样本含 PDF 页码 + 16 语法点）

## 交付物清单（本代理所有文件）
- apps/api/scripts/parse_syllabus.py（v2：5–9 级词表 + 语法表结构化提取）
- apps/api/scripts/build_hsk_kb.py（v2：等级带规范化 + MANUAL_POS 98 + 元数据）
- apps/api/scripts/audit_hsk_kb.py（v2：11000 行校验 + 双来源语法 verify + 高等级抽样）
- apps/api/scripts/grammar_points.json（518 条，schema_version 2）
- apps/api/app/content/hsk_kb.json（4.7MB，kb_version 2.0.0）
- apps/api/app/realtime/tools.py（v2 检索层）
- apps/api/tests/test_hsk_kb.py（+5 高等级/等级带用例）、tests/test_tools.py（版本断言同步）
- docs/architecture/hsk-kb-sources.md（解析范围 + 带 schema 决策）、hsk-kb-validation.md（再生成）

## 遗留/交接给主空间
1. **未做浏览器冒烟与真实供应商复验**（按约定由主空间统一执行）
2. 未重启 3000/8000 服务；验收重启由主空间收尾统一做
3. 100 条人工词性填充（98 新 + 你好 + 1 旧）待用户过目；test_review_migration 并发 flaky
   为既有问题（孤立重跑 intermittently 失败），建议主空间单独排查
4. HSKK 口试大纲映射、exam_format/topics_tasks 层、向量检索仍未做（Phase 2 范围外）
5. 语法点存在同名跨级条目（如 程度副词 L1–L7 各一条），document_id 按名称生成会重名，
   检索结果以 title+level 区分——如需唯一 document_id 可在后续版本加等级后缀
