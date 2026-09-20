"""Build hsk_kb.json from the parsed official syllabus draft plus seed enrichments.

Inputs:
- data/sources/parsed/vocab_l1_9_draft.json   (parse_syllabus.py output, 11000 rows:
  levels 1-6 plus the 7-9 band; band rows carry the level tag "7-9")
- data/sources/seeds/complete-hsk-vocabulary/complete.json
    (MIT, Yanis Zafirópulos 2026 — radical/frequency/old-level enrichment,
    pos fill for rows whose pos cell is empty in the official PDF)
- app/content/course_catalog_v2.json          (lesson examples for matched words)
- scripts/grammar_points.json                 (full grammar seed: all outline
    items levels 1-6 + 7-9 band, project-authored examples; structures
    verified against the official grammar outline by audit_hsk_kb.py)

Output: app/content/hsk_kb.json (schema v0.1 + level_band field, see
docs/architecture/hsk-knowledge-base-plan.md §4 and hsk-kb-sources.md)

Level policy: the official 2025-11 outline is authoritative for level_new.
The 7-9 band is stored as level_new=7 with level_note="（7-9）" and the
explicit field level_band="7-9" (backward-compatible: level_new stays an
int; consumers that need band semantics check level_band). Seed new-*/
newest-* tags are NOT used for level_new; disagreements are reported by
audit_hsk_kb.py, not silently merged.

Run: uv run --project apps/api python apps/api/scripts/build_hsk_kb.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
SOURCES = API_ROOT / "data" / "sources"
PARSED = SOURCES / "parsed"
SEED_DIR = SOURCES / "seeds" / "complete-hsk-vocabulary"
CONTENT = API_ROOT / "app" / "content"
OUT_FILE = CONTENT / "hsk_kb.json"

POS_SEED_TO_OFFICIAL = {
    "n": "名",
    "nr": "名",
    "ns": "名",
    "nt": "名",
    "nx": "名",
    "nz": "名",
    "v": "动",
    "vd": "动",
    "vg": "动",
    "vn": "动",
    "a": "形",
    "ad": "副",
    "an": "形",
    "b": "形",
    "z": "形",
    "d": "副",
    "dg": "副",
    "p": "介",
    "c": "连",
    "u": "助",
    "y": "助",
    "e": "叹",
    "o": "叹",
    "m": "数",
    "mg": "数",
    "q": "量",
    "r": "代",
    "rg": "代",
    "f": "名",
    "s": "名",
    "t": "名",
    "tg": "名",
    "h": "前缀",
    "k": "后缀",
    "l": "短语",
    "i": "成语",
}

# Manual pos fill for rows the seed does not cover (official PDF pos cell is
# empty AND drkameleon has no entry). Mostly four-character idioms (成语);
# flagged for human review in the audit. 你好 was filled in Phase 1.
MANUAL_POS = {
    "你好": ["叹"],
    "各行各业": ["成语"],
    "中华民族": ["名"],
    "多才多艺": ["成语"],
    "人山人海": ["成语"],
    "包罗万象": ["成语"],
    "别具匠心": ["成语"],
    "冰山一角": ["成语"],
    "冰天雪地": ["成语"],
    "不厌其烦": ["成语"],
    "不正之风": ["成语"],
    "不耻下问": ["成语"],
    "不可或缺": ["成语"],
    "不折不扣": ["成语"],
    "不知所措": ["成语"],
    "成家立业": ["成语"],
    "愁眉苦脸": ["成语"],
    "出口成章": ["成语"],
    "垂头丧气": ["成语"],
    "打下手": ["动"],
    "当机立断": ["成语"],
    "德才兼备": ["成语"],
    "得心应手": ["成语"],
    "得意扬扬": ["成语"],
    "颠倒黑白": ["成语"],
    "丢三落四": ["成语"],
    "断章取义": ["成语"],
    "对牛弹琴": ["成语"],
    "对症下药": ["成语"],
    "多年来": ["名"],
    "风吹雨打": ["成语"],
    "风雨无阻": ["成语"],
    "凤毛麟角": ["成语"],
    "古今中外": ["成语"],
    "顾名思义": ["成语"],
    "刮目相看": ["成语"],
    "汗马功劳": ["成语"],
    "忽冷忽热": ["成语"],
    "胡思乱想": ["成语"],
    "焕然一新": ["成语"],
    "绘声绘色": ["成语"],
    "集思广益": ["成语"],
    "急中生智": ["成语"],
    "见利忘义": ["成语"],
    "脚踏实地": ["成语"],
    "皆大欢喜": ["成语"],
    "锦上添花": ["成语"],
    "精彩纷呈": ["成语"],
    "井底之蛙": ["成语"],
    "救死扶伤": ["成语"],
    "居安思危": ["成语"],
    "居高不下": ["成语"],
    "举棋不定": ["成语"],
    "侃侃而谈": ["成语"],
    "刻舟求剑": ["成语"],
    "来之不易": ["成语"],
    "狼吞虎咽": ["成语"],
    "乐此不疲": ["成语"],
    "礼尚往来": ["成语"],
    "埋头苦干": ["成语"],
    "眉开眼笑": ["成语"],
    "梦寐以求": ["成语"],
    "难得一见": ["成语"],
    "南辕北辙": ["成语"],
    "鹏程万里": ["成语"],
    "岂有此理": ["成语"],
    "千姿百态": ["成语"],
    "琴棋书画": ["成语"],
    "求同存异": ["成语"],
    "如痴如醉": ["成语"],
    "时好时坏": ["成语"],
    "受宠若惊": ["成语"],
    "受益匪浅": ["成语"],
    "数一数二": ["成语"],
    "束手无策": ["成语"],
    "水滴石穿": ["成语"],
    "顺其自然": ["成语"],
    "四通八达": ["成语"],
    "糖尿病": ["名"],
    "掏腰包": ["动"],
    "无边无际": ["成语"],
    "无价之宝": ["成语"],
    "五湖四海": ["成语"],
    "鲜为人知": ["成语"],
    "小菜一碟": ["成语"],
    "心甘情愿": ["成语"],
    "揠苗助长": ["成语"],
    "掩耳盗铃": ["成语"],
    "一毛不拔": ["成语"],
    "一针见血": ["成语"],
    "因地制宜": ["成语"],
    "与时俱进": ["成语"],
    "源远流长": ["成语"],
    "晕头转向": ["成语"],
    "运筹帷幄": ["成语"],
    "在所难免": ["成语"],
    "纸上谈兵": ["成语"],
    "捉迷藏": ["动"],
    "足不出户": ["成语"],
}

OUTLINE_URL = "https://hsk.cn-bj.ufileos.com/3.0/新版HSK考试大纲1219.pdf"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def split_sense(word: str) -> tuple[str, int | None]:
    """点1 -> (点, 1); 二/两 -> unchanged."""
    match = re.fullmatch(r"(.+?)(\d+)", word)
    if match and re.fullmatch(r"[一-鿿]+", match.group(1)):
        return match.group(1), int(match.group(2))
    return word, None


def parse_official_pos(raw: str) -> list[str]:
    """形、（副）、（动） -> ["形", "副", "动"]"""
    if not raw:
        return []
    return [part.strip() for part in re.sub(r"[（）()]", "", raw).split("、") if part.strip()]


def seed_old_level(entry: dict) -> int | None:
    olds = [int(tag.split("-")[1]) for tag in entry.get("level", []) if tag.startswith("old-")]
    return min(olds) if olds else None


def build_vocabulary(vocab_draft: list[dict], seed_index: dict, lessons: list[dict]) -> list[dict]:
    # Map word -> lesson examples whose targets contain the word.
    lesson_examples: dict[str, list[dict]] = {}
    for entry in lessons:
        lesson = entry["lesson"]
        for target in lesson.get("targets", []):
            if len(target) < 2:
                continue
            for example in lesson.get("examples", [])[:1]:
                lesson_examples.setdefault(target, []).append(
                    {
                        "zh": example["chinese"],
                        "pinyin": example.get("pinyin", ""),
                        "support_text": example.get("support_text", ""),
                        "source": f"course:campus-chinese-foundations/{lesson['slug']}",
                    }
                )

    records = []
    for row in vocab_draft:
        word, sense = split_sense(row["word"])
        base_level = int(re.match(r"\d+", row["level"]).group())
        band = "7-9" if row["level"] == "7-9" else None
        parts = re.findall(r"[（(]([^）)]+)[）)]", row["level"])
        note = "".join(f"（{part}）" for part in parts) or None
        if band:
            note = f"（{band}）"
        seed = seed_index.get(word)

        pinyin = row["pinyin"]
        pos_official = parse_official_pos(row["pos"])
        pos_source = "syllabus"
        pos = pos_official
        if not pos:
            if seed and seed.get("pos"):
                pos = []
                for code in seed["pos"]:
                    mapped = POS_SEED_TO_OFFICIAL.get(code, code)
                    if mapped not in pos:
                        pos.append(mapped)
                pos_source = "seed:drkameleon"
            else:
                pos = MANUAL_POS.get(word, [])
                pos_source = "manual:project"

        forms = (seed or {}).get("forms") or [{}]
        meanings = forms[0].get("meanings", [])
        records.append(
            {
                "word": word,
                "sense": sense,
                "pinyin": pinyin,
                "pinyin_source": "syllabus",
                "pos": pos,
                "pos_source": pos_source,
                "level_new": base_level,
                "level_old": seed_old_level(seed) if seed else None,
                "level_note": note,
                "level_band": band,
                "radical": (seed or {}).get("radical"),
                "frequency": (seed or {}).get("frequency"),
                "gloss": [g.strip()[:100] for gloss in meanings[:1] for g in gloss.split(";")][:3],
                "examples": lesson_examples.get(word, []),
                "source": "HSK3.0-SYLLABUS",
            }
        )
    return records


def build_grammar(points: list[dict]) -> list[dict]:
    records = []
    for point in points:
        records.append(
            {
                "point": point["point"],
                "level": point["level"],
                "also_at": point.get("also_at", []),
                "category": point["category"],
                "structure": point["structure"],
                "examples": [
                    {**point["example"], "source": point["example_source"]},
                ],
                "related_points": point.get("related", []),
                "source": f"HSK3.0-SYLLABUS-GRAMMAR-L{point['level']}",
            }
        )
    return records


def main() -> None:
    vocab_draft = load_json(PARSED / "vocab_l1_9_draft.json")
    grammar_points = load_json(SCRIPT_DIR / "grammar_points.json")["points"]
    seed = load_json(SEED_DIR / "complete.json")
    seed_index = {entry["simplified"]: entry for entry in seed}
    catalog = load_json(CONTENT / "course_catalog_v2.json")

    vocabulary = build_vocabulary(vocab_draft, seed_index, catalog["lessons"])
    grammar = build_grammar(grammar_points)
    sha = load_json(PARSED / "parse_report.json")["source_sha256"]
    counts = {
        "vocabulary": len(vocabulary),
        "vocabulary_by_level": {
            str(level): sum(1 for v in vocabulary if v["level_new"] == level)
            for level in (1, 2, 3, 4, 5, 6, 7)
        },
        "vocabulary_band_7_9": sum(1 for v in vocabulary if v["level_band"] == "7-9"),
        "grammar": len(grammar),
        "grammar_by_level": {
            str(level): sum(1 for g in grammar if g["level"] == level)
            for level in (1, 2, 3, 4, 5, 6, 7)
        },
        "vocab_with_lesson_examples": sum(1 for v in vocabulary if v["examples"]),
        "vocab_pos_from_seed": sum(1 for v in vocabulary if v["pos_source"] == "seed:drkameleon"),
        "vocab_pos_manual": sum(1 for v in vocabulary if v["pos_source"] == "manual:project"),
    }
    kb = {
        "metadata": {
            "kb_id": "hsk-kb",
            "kb_version": "2.0.0",
            "standard": "HSK3.0",
            "version": "2025-11修订版（2026-07-01 实施）",
            "lastUpdated": datetime.now(UTC).date().isoformat(),
            "levels_included": [1, 2, 3, 4, 5, 6, 7],
            "band_note": (
                "HSK3.0 七至九级为一个等级带；词表中等级标记为 7-9 的词以"
                "level_new=7 + level_band=\"7-9\" + level_note=\"（7-9）\" 入库（向后兼容），"
                "检索层将 HSK7/8/9 与七/八/九级查询全部映射到该等级带。"
            ),
            "counts": counts,
            "sources": [
                {
                    "id": "HSK3.0-SYLLABUS",
                    "title": "新版《HSK考试大纲》（中文水平考试 HSK 考试大纲）",
                    "publisher": "中外语言交流合作中心 / 汉考国际（2025-11 发布，2026-07 实施）",
                    "url": OUTLINE_URL,
                    "sha256": sha,
                    "license": "官方大纲事实性数据（词表/语法点/结构）；例句与教材原文不入库",
                    "role": "等级/词语/拼音/词性/语法结构的权威来源",
                },
                {
                    "id": "SEED-DRKAMELEON",
                    "title": "drkameleon/complete-hsk-vocabulary complete.json",
                    "publisher": "Yanis Zafirópulos (GitHub)",
                    "url": "https://github.com/drkameleon/complete-hsk-vocabulary",
                    "license": "MIT（再分发需保留声明）；词义来自 CC-CEDICT（CC BY-SA 4.0）",
                    "role": "部首/词频/旧2.0等级 enrichment；官方空词性格的填充"
                    "（Phase1-2 共 397 词）",
                },
                {
                    "id": "COURSE-CATALOG-V2",
                    "title": "项目课程 course_catalog_v2.json",
                    "publisher": "HanziMate 项目自编",
                    "license": "项目自有内容",
                    "role": "匹配词条的例句来源（标注到课程 slug）",
                },
            ],
            "grammar_seed": (
                "scripts/grammar_points.json（官方语法大纲全量细目"
                "+项目自编例句，经 audit 校验）"
            ),
            "notes": (
                "level_new 以官方 2025-11 大纲为准；level_old 为 HSK 2.0 旧等级（种子数据）。"
                "exam_format 与 topics_tasks 层留待后续阶段填充。"
            ),
        },
        "vocabulary": vocabulary,
        "grammar": grammar,
        "exam_format": [],
        "topics_tasks": [],
    }
    OUT_FILE.write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT_FILE} ({OUT_FILE.stat().st_size} bytes)")
    print(json.dumps(counts, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
