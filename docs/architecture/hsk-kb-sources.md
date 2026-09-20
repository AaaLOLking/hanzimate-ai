# HSK 知识库来源清单（Phase 0 产出，Phase 2 更新）

生成日期：2026-09-18；Phase 2（高等级扩展）更新：2026-09-19。配套验收文档：[hsk-kb-validation.md](./hsk-kb-validation.md)；建设计划：[hsk-knowledge-base-plan.md](./hsk-knowledge-base-plan.md)。

存放策略（用户已确认的默认决策）：来源 PDF 本体与种子仓库**不入 git**（`apps/api/data/sources/` 已加入 .gitignore），本文档记录 URL、下载日期、SHA-256 与许可证结论，管线可随时重下复现。

## 1. 官方资料（apps/api/data/sources/）

| 文件 | 内容 | 来源 URL（实测可达） | 下载日期 | SHA-256 |
|---|---|---|---|---|
| hsk3-syllabus-outline.pdf | 新版《HSK考试大纲》（中文水平考试），中外语言交流合作中心发布，**2025-11 发布、2026-07 实施**，406 页，含任务/话题/词汇/汉字/语法大纲（一至九级）。**知识库的等级权威来源** | `https://hsk.cn-bj.ufileos.com/3.0/新版HSK考试大纲1219.pdf`（URL 编码形式下载，HTTP 200，4,636,209 字节） | 2026-09-18 | ec74ce0439e837bbb15154be13e747ae798903b2fd3a331629df6c3b45504941 |
| hskk-speaking-outline.pdf | HSKK 口语考试大纲（初/中/高级题型：听后重复、看图说话等），32 页。**Phase 2 口语模式映射用，Phase 1 未解析** | `https://www.chinesetest.cn/userfiles/file/dagang/HSK-koushi.pdf` | 2026-09-18 | d9939dcb61eaa43b62bcaa844c9bc3a382a833244e9d2602701df31d78f8a0ea |
| H1_DG.pdf … H6_DG.pdf | HSK 一至六级（2.0 体系）各级大纲，7–8 页/级，主要为考试说明+样题 | `https://download.chinesetest.cn/newhsk-site/Syllabus/H{1..6}_DG.pdf`（全部 HTTP 200） | 2026-09-18 | 见 `data/sources/sha256sums.txt`（H1: 5465be1d… / H2: 112e2c05… / H3: 5bda3cdd… / H4: c0735ba2… / H5: e00737de… / H6: 70f0c7d3…） |

已探测但不存在（404，记录备查）：`download.chinesetest.cn/newhsk-site/Syllabus/HSKK_DG.pdf`、`HSKK1/2/3_DG.pdf` —— HSKK 各级大纲无此命名，口语大纲以 `hskk-speaking-outline.pdf` 为准。

版权结论：大纲的**事实性数据**（词表、等级、语法点列表、题型结构）入库使用；教材与真题原文不入库（计划 §6 风险节）。

## 2. 种子仓库（apps/api/data/sources/seeds/，git clone --depth 1）

| 仓库 | LICENSE 结论 | 本库使用方式 |
|---|---|---|
| `drkameleon/complete-hsk-vocabulary`（complete.json，11,470 词条） | **MIT License，Copyright (c) 2026 Yanis Zafirópulos —— 允许再分发/修改，需保留版权与许可声明**（LICENSE 文件实测在库） | 允许入库。用途：部首/词频/旧 2.0 等级（level_old）enrichment；22 个官方空词性格的填充（pos_source=seed:drkameleon）；等级交叉核对参照。其词义来自 CC-CEDICT（CC BY-SA 4.0，已在 hsk_kb.json 元数据署名），部首来自 makemeahanzi |
| `clem109/hsk-vocabulary`（hsk-level-1..6.json，2.0 词表+少量例句） | **MIT License，Copyright (c) 2018 Clement Venard —— 允许再分发** | 允许入库，但实测 L1–4 共 1,200 词中仅 1 个带例句（保护），**Phase 1 未采用其数据**；留作 Phase 2 例句层候选 |

两仓库 LICENSE 均为 MIT，无不允许再分发的数据。

## 3. 项目自有来源

- `apps/api/app/content/course_catalog_v2.json`（项目自编课程）：仅作为**例句来源**按 target 匹配挂接到词条（18 个词带课程例句），来源标注到课程 slug。
- `apps/api/scripts/grammar_points.json`（项目语法点全量表，518 条）：HSK1–6 级与七—九级带的全部语法细目；structure/verify 摘自官方语法大纲原文（audit 逐条校验 verify 文本出现在大纲对应等级章节——1–4 级同时对照行文本草稿与结构化提取两个独立来源）；例句为项目自编或引自上述课程，逐条标注 example_source。其中 112 条沿用 Phase 1 精选（provenance.reused_curated=true）。

## 4. 重跑管线

```
uv run --project apps/api python apps/api/scripts/parse_syllabus.py   # PDF → 草稿（自检断言）
uv run --project apps/api python apps/api/scripts/build_hsk_kb.py     # 草稿+种子 → app/content/hsk_kb.json
uv run --project apps/api python apps/api/scripts/audit_hsk_kb.py     # 审计 + 生成抽样对照表
```

解析范围（Phase 2 扩展）：词表 PDF 第 79–354 页（序号 1–11000：L1=300/L2=200/L3=500/L4=1000/L5=1600/L6=1800/七—九级带=5600）；语法大纲 PDF 第 386–406 页（HSK（一级）…（七—九级）语法，结构化提取 312 个细目条目，按复句/固定格式/固定短语行拆分后入库 518 点）。词表坐标行聚类不变；语法表改用 `find_tables` 单元格几何（每表按表头单元格定列边界，各页列 x 位置不同），水印字形按字号（>20pt）剔除，且校验除页脚/标题外所有字符均被单元格覆盖。

审计当前结论：11000 词 + 518 语法点，0 失败；种子等级交叉核对 10087 与 newest-* 一致、65 条不一致（多为多义词条目，以官方大纲为准，仅报告）、839 词不在种子（多为 2025-11 新收词）相应字段为 null；官方空词性格 397 条由种子填充、100 条人工填充（98 个五至九级成语/名词/动词 + Phase 1 的「你好」，**待人工过目**）。

**七—九级带 schema 决策**（向后兼容）：3.0 体系七至九级为一个等级带，官方词表等级列直接印「7-9」。入库时 `level_new` 保持 int=7，新增可选字段 `level_band="7-9"`，`level_note="（7-9）"`（与 1–4 级交叉引用注记格式一致）；检索层 `query_level_filter`/`level_hit_filter` 将 HSK7/8/9 与「七/八/九级」全部映射到该带（BAND_LEVELS={7,8,9}），条目等级显示为「HSK7-9」。语法大纲本身按「HSK（七—九级）语法」一章呈现，level=7 即带内等级。
