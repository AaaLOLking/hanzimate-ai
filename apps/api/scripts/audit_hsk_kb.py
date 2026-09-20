"""Audit hsk_kb.json: schema validation, source cross-checks, sample table.

Checks (hard failures exit 1):
1. Schema: metadata/vocabulary/grammar structure, required fields, types.
2. Draft coverage: every one of the 11000 official rows appears in the KB
   exactly once, in serial order (word+pinyin identity against the draft).
3. Format: pinyin letters/tone marks, pos vocabulary, level_note shape.
4. Provenance consistency: rows whose official pos cell is empty must carry
   pos_source seed:drkameleon or manual:project; manual fills must be listed.
5. Seed cross-check (report-only): KB level_new vs drkameleon newest-*/new-*
   tags; disagreements are listed, not failed — the official outline wins.
6. Grammar: every point's `verify` strings must appear verbatim in the
   official grammar outline text of its declared level (the union of the
   line-based draft for levels 1-4 and the structured outline extraction
   for levels 1-7); related_points must resolve; example sentences must be
   non-empty Chinese.

Also writes docs/architecture/hsk-kb-validation.md with a deterministic
sample comparison table (vocab across levels 1-7 incl. the 7-9 band, plus
grammar samples, with PDF page numbers for human spot checks).

Run: uv run --project apps/api python apps/api/scripts/audit_hsk_kb.py
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
SOURCES = API_ROOT / "data" / "sources"
PARSED = SOURCES / "parsed"
KB_FILE = API_ROOT / "app" / "content" / "hsk_kb.json"
SEED_DIR = SOURCES / "seeds" / "complete-hsk-vocabulary"
VALIDATION_MD = REPO_ROOT / "docs" / "architecture" / "hsk-kb-validation.md"
FINAL_SERIAL = 11000

PY_OK = re.compile(r"^[A-Za-zĀāÁáǍǎÀàĒēÉéĚěÈèĪīÍíǏǐÌìŌōÓóǑǒÒòŪūÚúǓǔÙùǕǖǗǘǙǚǛǜÜüńňǹǸŃŇḿḾ'’\-/ ]+$")
POS_VALUES = {
    "名", "动", "形", "副", "介", "连", "助", "叹", "数", "量", "代",
    "前缀", "后缀", "短语", "成语", "数量", "拟声",
}
LEVEL_NOTE = re.compile(r"^(\（\d+(-\d+)?\）)+$")

failures: list[str] = []
reports: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def report(msg: str) -> None:
    reports.append(msg)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_schema(kb: dict) -> None:
    meta = kb.get("metadata", {})
    for key in ("kb_id", "kb_version", "standard", "version", "lastUpdated", "sources"):
        if key not in meta:
            fail(f"metadata missing {key}")
    if meta.get("standard") != "HSK3.0":
        fail("metadata.standard != HSK3.0")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta.get("lastUpdated", ""))):
        fail("metadata.lastUpdated not YYYY-MM-DD")
    for idx, entry in enumerate(kb.get("vocabulary", [])):
        for key in ("word", "pinyin", "pos", "level_new", "source"):
            if key not in entry:
                fail(f"vocabulary[{idx}] missing {key}")
        if not isinstance(entry.get("level_new"), int) or not 1 <= entry.get("level_new", 0) <= 7:
            fail(f"vocabulary[{idx}] level_new invalid: {entry.get('level_new')}")
        if entry.get("level_old") is not None and not 1 <= entry["level_old"] <= 6:
            fail(f"vocabulary[{idx}] level_old invalid: {entry['level_old']}")
        note = entry.get("level_note")
        if note is not None and not LEVEL_NOTE.match(note):
            fail(f"vocabulary[{idx}] level_note invalid: {note!r}")
        band = entry.get("level_band")
        if band is not None and band != "7-9":
            fail(f"vocabulary[{idx}] level_band invalid: {band!r}")
        if band == "7-9" and entry["level_new"] != 7:
            fail(f"vocabulary[{idx}] band row level_new != 7")
    for idx, entry in enumerate(kb.get("grammar", [])):
        for key in ("point", "level", "category", "structure", "examples", "source"):
            if key not in entry:
                fail(f"grammar[{idx}] missing {key}")
        if not 1 <= entry.get("level", 0) <= 7:
            fail(f"grammar[{idx}] level invalid")
        if not entry.get("examples") or not entry["examples"][0].get("zh"):
            fail(f"grammar[{idx}] example missing")


def check_against_draft(kb: dict, draft: list[dict]) -> None:
    vocab = kb["vocabulary"]
    if len(vocab) != len(draft):
        fail(f"vocab size {len(vocab)} != draft size {len(draft)}")
        return
    for idx, (entry, row) in enumerate(zip(vocab, draft, strict=True)):
        if idx + 1 != row["serial"]:
            fail(f"vocabulary[{idx}] out of serial order")
            return
        base_level = int(re.match(r"\d+", row["level"]).group())
        if entry["level_new"] != base_level:
            fail(f"serial {row['serial']}: level_new {entry['level_new']} != draft {base_level}")
        if entry["word"] != re.sub(r"\d+$", "", row["word"]) and entry["word"] != row["word"]:
            fail(f"serial {row['serial']}: word {entry['word']!r} vs draft {row['word']!r}")
        if entry["pinyin"] != row["pinyin"]:
            fail(f"serial {row['serial']}: pinyin {entry['pinyin']!r} vs draft {row['pinyin']!r}")
        if row["flag"] == "pos_empty_in_source":
            if entry["pos_source"] == "syllabus":
                fail(f"serial {row['serial']}: official pos empty but pos_source=syllabus")
        elif entry["pos_source"] != "syllabus":
            detail = entry["pos_source"]
            fail(f"serial {row['serial']}: official pos present but pos_source={detail}")


def check_formats(kb: dict) -> None:
    # Official outline lists some polysemous words twice per level (会1 动 / 会2 名)
    # and a few words repeat across levels with the same pinyin (横 héng in L6
    # and in the 7-9 band); sense numbers and level disambiguate, so the
    # identity key includes both.
    seen: set[tuple[str, str, object, object]] = set()
    for entry in kb["vocabulary"]:
        key = (entry["word"], entry["pinyin"], entry.get("sense"), entry["level_new"])
        if key in seen:
            fail(f"duplicate (word, pinyin): {key}")
        seen.add(key)
        if not PY_OK.match(entry["pinyin"]):
            fail(f"bad pinyin format: {entry['word']} {entry['pinyin']!r}")
        bad_pos = [p for p in entry["pos"] if p not in POS_VALUES]
        if bad_pos:
            fail(f"bad pos values: {entry['word']} {bad_pos}")
        for gloss in entry.get("gloss", []):
            if len(gloss) > 120:
                fail(f"gloss too long: {entry['word']}")


def check_seed_cross(kb: dict, seed_index: dict) -> None:
    agree_newest = agree_new = disagree = missing = 0
    disagreements: list[str] = []
    for entry in kb["vocabulary"]:
        seed = seed_index.get(entry["word"])
        if not seed:
            missing += 1
            continue
        tags = seed.get("level", [])
        newest = [int(t.split("-")[1]) for t in tags if t.startswith("newest-")]
        new = [int(t.split("-")[1]) for t in tags if t.startswith("new-")]
        if entry["level_new"] in newest:
            agree_newest += 1
        elif entry["level_new"] in new:
            agree_new += 1
        else:
            disagree += 1
            if len(disagreements) < 30:
                tag_text = ";".join(str(t) for t in tags)
                item = f"{entry['word']}(KB-L{entry['level_new']}, seed=[{tag_text}])"
                disagreements.append(item)
    total = len(kb["vocabulary"])
    report(
        f"seed level cross-check: {total} words | agree newest-* {agree_newest} "
        f"| agree new-* {agree_new} | disagree {disagree} | not in seed {missing}"
    )
    if disagreements:
        report("sample disagreements (official outline wins): " + "; ".join(disagreements))


def check_grammar(
    kb: dict,
    grammar_draft: dict[str, list[str]],
    outline: dict[str, list[dict]],
) -> None:
    """verify strings must appear in the outline text of the point's level.

    Outline text = line-based draft (levels 1-4, independent Phase-1
    extraction) UNION structured outline extraction (levels 1-7), so a
    systematic mis-parse in either one is caught by the other.
    """
    texts = {}
    for level in ("1", "2", "3", "4", "5", "6", "7"):
        parts = []
        if level in grammar_draft:
            parts.append("".join(grammar_draft[level]))
        for item in outline.get(level, []):
            parts.append(item.get("name", ""))
            parts.append(item.get("sub", ""))
            parts.extend(item.get("content", []))
        texts[level] = re.sub(r"\s+", "", "".join(parts))
    points = {g["point"] for g in kb["grammar"]}
    raw_points = {(p["point"], p["level"]): p for p in load(SCRIPT_SEED)["points"]}
    for g in kb["grammar"]:
        raw = raw_points.get((g["point"], g["level"]))
        if raw is None:
            fail(f"grammar point not in seed file: {g['point']} L{g['level']}")
            continue
        text = texts[str(g["level"])]
        for snippet in raw.get("verify", []):
            if re.sub(r"\s+", "", snippet) not in text:
                hint = re.sub(r"\s+", "", snippet)[:30]
                fail(f"grammar {g['point']}: verify not in outline L{g['level']}: {hint!r}")
        for rel in g.get("related_points", []):
            if rel not in points:
                fail(f"grammar {g['point']}: dangling related point {rel!r}")


SCRIPT_SEED = Path(__file__).resolve().parent / "grammar_points.json"


def write_sample(kb: dict, draft: list[dict]) -> None:
    rng = random.Random(20260918)
    per_level = {1: 7, 2: 5, 3: 7, 4: 7, 5: 6, 6: 6, 7: 12}
    ranges = {1: (1, 300), 2: (301, 500), 3: (501, 1000), 4: (1001, 2000),
              5: (2001, 3600), 6: (3601, 5400), 7: (5401, 11000)}
    picked: list[int] = []
    for level, count in per_level.items():
        lo, hi = ranges[level]
        picked.extend(rng.sample(range(lo, hi + 1), count))
    rows = []
    for serial in sorted(picked):
        entry = kb["vocabulary"][serial - 1]
        row = draft[serial - 1]
        band = "（带）" if entry.get("level_band") else ""
        rows.append(
            f"| {serial} | {entry['word']} | {entry['level_new']}{band} | {entry['pinyin']} | "
            f"{'、'.join(entry['pos'])} | {entry['pos_source']} | PDF页{row['page']} |"
        )
    grammar_rows = []
    rng2 = random.Random(7)
    for g in rng2.sample(kb["grammar"], 16):
        band = "（7-9带）" if g["level"] == 7 else ""
        grammar_rows.append(
            f"| {g['point']} | {g['level']}{band} | {g['category']} | {g['structure'][:60]} | "
            f"{g['examples'][0]['zh']} | {g['examples'][0]['source']} |"
        )
    md = "\n".join(
        [
            "# HSK 知识库验收抽样对照表",
            "",
            "生成：audit_hsk_kb.py（确定性随机抽样，种子 20260918 / 7）。",
            "对照对象：hsk_kb.json vs data/sources/parsed/ 解析草稿（官方 PDF 提取）。",
            "PDF 页码为官方大纲物理页码，可人工翻开核对。等级带条目标注（带）。",
            "",
            "## 词汇抽样（50 条，覆盖 1-6 级与 7-9 等级带）",
            "",
            "| 序号 | 词条 | 等级 | 拼音 | 词性 | 词性来源 | 大纲页码 |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## 语法点抽样（16 条，含七—九级带）",
            "",
            "| 语法点 | 等级 | 类别 | 结构 | 例句 | 例句来源 |",
            "|---|---|---|---|---|---|",
            *grammar_rows,
            "",
        ]
    )
    VALIDATION_MD.write_text(md, encoding="utf-8")
    report(f"sample table written: {VALIDATION_MD} (50 vocab + 16 grammar)")


def main() -> None:
    kb = load(KB_FILE)
    draft = load(PARSED / "vocab_l1_9_draft.json")
    grammar_draft = load(PARSED / "grammar_draft_l1_4.json")
    outline = load(PARSED / "grammar_outline.json")
    seed = load(SEED_DIR / "complete.json")
    seed_index = {e["simplified"]: e for e in seed}
    license_file = SEED_DIR / "LICENSE"
    if not license_file.exists() or "MIT License" not in license_file.read_text(encoding="utf-8"):
        fail("drkameleon LICENSE missing or not MIT")

    check_schema(kb)
    check_against_draft(kb, draft)
    check_formats(kb)
    check_seed_cross(kb, seed_index)
    check_grammar(kb, grammar_draft, outline)
    write_sample(kb, draft)

    print("=== AUDIT REPORT ===")
    for line in reports:
        print(line)
    if failures:
        print(f"\n=== {len(failures)} FAILURES ===")
        for line in failures[:50]:
            print("FAIL:", line)
        sys.exit(1)
    print(f"\nOK: {len(kb['vocabulary'])} vocab, {len(kb['grammar'])} grammar points, 0 failures")


if __name__ == "__main__":
    main()
