"""Parse the official HSK 3.0 syllabus outline PDF into structured drafts.

Source: apps/api/data/sources/hsk3-syllabus-outline.pdf
(新版《HSK考试大纲》, 汉考国际, 2025-11 发布 2026-07 实施, downloaded from
https://hsk.cn-bj.ufileos.com/3.0/新版HSK考试大纲1219.pdf)

Outputs (all under apps/api/data/sources/parsed/, git-ignored, regenerable):
- vocab_l1_9_draft.json: full vocabulary table serials 1-11000
  (levels 1-6 plus the 7-9 band), one record per official row with page
  provenance and per-field flags.
- grammar_outline.json: structured grammar outline items for levels 1-7
  (level 7 = the official 七—九级 band), extracted from table cell geometry.
- grammar_draft_l1_4.json: cleaned outline text of the grammar sections
  (HSK（一级）语法 ... HSK（四级）语法) — kept for cross-checking.
- parse_report.json: counts and integrity checks (serial continuity etc.).

Extraction strategy: PyMuPDF word coordinates grouped into rows by y position
and columns by x position. Row acceptance requires the serial number to be
exactly previous+1, which makes gaps/duplicates impossible to miss. Grammar
tables use find_tables cell geometry with watermark glyphs (font size > 20)
removed; every remaining character must be claimed by exactly one cell.

Known source-data quirks (verified in Phase 1/2):
- Levels 1-4: 22 rows have an EMPTY pos cell (pinyin printed as two
  space-separated syllables). Levels 5-9: 473 rows have an EMPTY pos cell
  (same quirk plus idioms); build_hsk_kb.py fills pos from the MIT-licensed
  drkameleon seed (375 rows) or manual fills (98 rows, listed in
  build_hsk_kb.py MANUAL_POS) and marks pos_source accordingly.
- Three rows carry the pos value 拟声 (哈/哇/轰), added to POSLIKE in Phase 2.
- Level tags may carry parenthesized cross-references, e.g. "1（2）（4）" or
  "2（7-9）"; the leading integer is the word's own level. The 7-9 band tag
  is the plain token "7-9" (serials 5401-11000, level_new=7 with
  level_note "（7-9）" — see docs/architecture/hsk-kb-sources.md).

Run: uv run --project apps/api python apps/api/scripts/parse_syllabus.py
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import fitz  # PyMuPDF

API_ROOT = Path(__file__).resolve().parents[1]
SOURCES = API_ROOT / "data" / "sources"
OUT_DIR = SOURCES / "parsed"
OUTLINE_PDF = SOURCES / "hsk3-syllabus-outline.pdf"

# Vocabulary table: PDF pages 79-354 (1-based) hold serials 1-11000.
# Grammar outline: pages 386-406 hold HSK（一级）...（七—九级）语法.
VOCAB_PAGES = (79, 354)
GRAMMAR_LEVEL_PAGES = {1: (386, 388), 2: (389, 391), 3: (392, 394), 4: (395, 397),
                       5: (398, 400), 6: (401, 402), 7: (403, 406)}
LEVEL_SERIAL_RANGES = {1: (1, 300), 2: (301, 500), 3: (501, 1000), 4: (1001, 2000),
                       5: (2001, 3600), 6: (3601, 5400), 7: (5401, 11000)}
FINAL_SERIAL = 11000

# Column x-ranges measured from the PDF (points): serial, level, word, pinyin.
COLS = {"serial": (55, 110), "level": (110, 200), "word": (200, 295), "pinyin": (295, 420)}
POS_MIN_X = 420
Y_TOL = 4.0  # pinyin glyphs sit up to ~3pt above/below the CJK baseline

DROP_TOKENS = {"汉考国际", "际", "汉"}
HEADER_TOKENS = {"序号", "等级", "词语", "拼音", "词性"}
LEVEL_TAG = re.compile(r"^\d+(\（[\d-]+\）)*$")
LEVEL_TAG_BAND = re.compile(r"^7-9$")
POSLIKE = re.compile(r"^(名|动|形|副|介|连|助|叹|数|量|代|前缀|后缀|拟声)")
WORDLIKE = re.compile(r"^[一-鿿A-Za-z0-9·]+$")
PY_LETTER = re.compile(r"[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹḿ'’\-/]")

# Grammar table header tokens and top-level (c0) section names.
G_HEADER_TOKENS = {"类别", "类别名称", "细目", "语法内容"}
G_CATS = {"语素", "词类", "短语", "句子成分", "句子的类型", "动作的态", "复句",
          "数的表达法", "时间表示法", "特殊表达法", "固定格式", "固定短语",
          "语段（句群）"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_of(x0: float) -> str | None:
    for name, (lo, hi) in COLS.items():
        if lo <= x0 < hi:
            return name
    if x0 >= POS_MIN_X:
        return "pos"
    return None


def extract_rows(page: fitz.Page) -> list[dict[str, list[str]]]:
    """Group word tokens into table rows keyed by y, columns keyed by x."""
    lines: dict[float, dict[str, list[str]]] = {}
    for x0, y0, _x1, _y1, text, *_ in page.get_text("words"):
        # NOTE: header tokens (序号/等级/词语/拼音/词性) must NOT be dropped:
        # 词语 is itself a level-4 vocabulary entry (serial 1098). The repeated
        # page header forms a line whose serial cell is non-numeric, so it is
        # skipped by the serial-continuity check anyway.
        if text in DROP_TOKENS:
            continue
        col = column_of(x0)
        if col is None:
            continue
        anchor = next((y for y in lines if abs(y - y0) < Y_TOL), None)
        if anchor is None:
            anchor = y0
            lines[anchor] = {name: [] for name in [*COLS, "pos"]}
        lines[anchor][col].append(text)
    return [lines[y] for y in sorted(lines)]


def parse_vocab(doc: fitz.Document) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    expected = 1
    for pno in range(VOCAB_PAGES[0] - 1, VOCAB_PAGES[1]):
        for line in extract_rows(doc[pno]):
            serial_txt = " ".join(line["serial"])
            if not serial_txt.isdigit():
                continue  # wrapped continuation line or page furniture
            serial = int(serial_txt)
            if serial != expected:
                continue  # page number / stray digit that is not the next row
            level = " ".join(line["level"])
            word = " ".join(line["word"])
            pinyin = " ".join(line["pinyin"])
            pos = " ".join(line["pos"])
            tag_ok = LEVEL_TAG.match(level) or LEVEL_TAG_BAND.match(level)
            if not tag_ok or not WORDLIKE.match(word):
                raise ValueError(f"serial {serial}: bad level/word: {level!r} {word!r}")
            if pinyin and not all(PY_LETTER.search(tok) for tok in pinyin.split()):
                raise ValueError(f"serial {serial}: suspicious pinyin {pinyin!r}")
            if pos and not POSLIKE.match(pos):
                raise ValueError(f"serial {serial}: suspicious pos {pos!r}")
            flag = ""
            if not pinyin:
                flag = "pinyin_empty_in_source"
            elif not pos:
                flag = "pos_empty_in_source"
            records.append(
                {
                    "serial": serial,
                    "level": level,
                    "word": word,
                    "pinyin": pinyin,
                    "pos": pos,
                    "page": pno + 1,
                    "flag": flag,
                }
            )
            expected += 1
            if serial >= FINAL_SERIAL:
                return records
    raise ValueError(f"table ended early: last serial {expected - 1}")


def check_level_columns(records: list[dict[str, object]]) -> list[str]:
    """Every row's level column must agree with its official serial range."""
    problems = []
    for level, (lo, hi) in LEVEL_SERIAL_RANGES.items():
        for rec in records:
            serial = int(rec["serial"])
            if lo <= serial <= hi and not str(rec["level"]).startswith(str(level)):
                problems.append(f"serial {serial}: level column {rec['level']!r}")
    return problems


def parse_grammar(doc: fitz.Document) -> dict[str, list[str]]:
    """Line-based draft of the grammar outline text (cross-check reference)."""
    drafts: dict[str, list[str]] = {}
    for level, (p1, p2) in GRAMMAR_LEVEL_PAGES.items():
        lines = []
        for pno in range(p1 - 1, p2):
            for raw in (doc[pno].get_text() or "").splitlines():
                text = raw.strip()
                if not text or text in DROP_TOKENS:
                    continue
                if re.fullmatch(r"-{3,}", text) or re.fullmatch(r"\d{3}", text):
                    continue
                if re.fullmatch(r"HSK（.+）语法", text):
                    continue
                lines.append(text)
        drafts[str(level)] = lines
    return drafts


# ---------------------------------------------------------------- grammar v2

def g_clean_chars(page: fitz.Page) -> list[tuple[float, float, float, float, str]]:
    """Characters of the page with watermark glyphs (font size > 20) removed."""
    chars = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["size"] > 20:
                    continue
                for ch in span["chars"]:
                    if ch["c"].strip():
                        chars.append((*ch["bbox"], ch["c"]))
    return chars


def g_cell_text(cell, chars, used):
    """Reading-order text of one cell (line grouping by y, x within line)."""
    toks = []
    for i, (x0, y0, x1, y1, c) in enumerate(chars):
        if i in used:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if cell.x0 - 1 <= cx <= cell.x1 + 1 and cell.y0 - 1 <= cy <= cell.y1 + 1:
            toks.append((y0, x0, i, c))
            used.add(i)
    if not toks:
        return ""
    lines = {}
    for y, x, _idx, c in toks:
        anchor = next((a for a in lines if abs(a - y) < 4.5), None)
        if anchor is None:
            anchor = y
            lines[anchor] = []
        lines[anchor].append((x, c))
    return " ".join("".join(c for _, c in sorted(lines[a])) for a in sorted(lines))


def g_header(text: str) -> bool:
    if text in G_HEADER_TOKENS or "语法内容" in text:
        return True
    return bool(re.fullmatch(r"HSK（.+）语法", text) or re.fullmatch(r"\d{3}", text))


def g_extract_page(page: fitz.Page, pno: int) -> tuple[list[dict[str, object]], str]:
    """Extract grammar items from one page.

    Column boundaries are derived per table from its header row cells
    (类别/类别名称/细目/语法内容) because column x-positions differ between
    pages (e.g. 细目 starts at x=186 on p392 but x=223 on p403).
    """
    chars = g_clean_chars(page)
    used: set[int] = set()
    items: list[dict[str, object]] = []
    for tab in page.find_tables().tables:
        filled = []
        for c in tab.cells:
            cell = fitz.Rect(c)
            text = g_cell_text(cell, chars, used)
            filled.append({"cell": cell, "text": text})
        header_x = sorted(
            f["cell"].x0 for f in filled if f["text"].strip() in G_HEADER_TOKENS
        )
        if len(header_x) < 4:
            continue

        def colof(x0, bounds=header_x):
            col = None
            for hi, hx in enumerate(bounds):
                if x0 >= hx - 2:
                    col = hi
            return col

        labels = []
        conts = []
        for f in filled:
            text = f["text"].strip()
            if not text or g_header(text):
                continue
            col = colof(f["cell"].x0)
            if col is None or col > 3:
                continue
            if col < 3:
                labels.append({"cell": f["cell"], "text": text, "col": col})
            else:
                conts.append({"cell": f["cell"], "text": text})
        if not labels and not conts:
            continue
        groups = {id(lab): [] for lab in labels}
        orphan = []
        for f in conts:
            yc = (f["cell"].y0 + f["cell"].y1) / 2
            if not labels:
                orphan.append((f["cell"].y0, f["text"]))
                continue
            containing = [lab for lab in labels
                          if lab["cell"].y0 - 1 <= yc <= lab["cell"].y1 + 1]
            if containing:
                owner = max(containing, key=lambda lab: lab["col"])
            else:
                def dist(lab, ycenter=yc):
                    c = lab["cell"]
                    return (min(abs(c.y0 - ycenter), abs(c.y1 - ycenter)), -lab["col"])
                owner = min(labels, key=dist)
            groups[id(owner)].append((f["cell"].y0, f["text"]))

        def has_child(lab, pool=labels):
            return any(
                m["col"] > lab["col"]
                and m["cell"].y1 > lab["cell"].y0 and m["cell"].y0 < lab["cell"].y1
                for m in pool
            )

        cats = [lab for lab in labels if lab["col"] == 0]
        names = [lab for lab in labels if lab["col"] == 1]
        for lab in labels:
            content = [t for _, t in sorted(groups[id(lab)])]
            if not content and has_child(lab):
                continue  # section header, not an item
            yc = (lab["cell"].y0 + lab["cell"].y1) / 2

            def pick(pool, ycenter=yc):
                best = ""
                for m in pool:
                    c = m["cell"]
                    if c.y0 - 1 <= ycenter <= c.y1 + 1:
                        return m["text"]
                    if c.y1 < ycenter:
                        best = m["text"]
                return best

            items.append({
                "cat": pick(cats),
                "name": lab["text"] if lab["col"] == 1 else pick(names),
                "sub": lab["text"] if lab["col"] == 2 else "",
                "content": content, "page": pno + 1,
            })
        if orphan:
            items.append({"cat": "", "name": "", "sub": "",
                          "content": [t for _, t in sorted(orphan)],
                          "page": pno + 1})
    leftover = "".join(chars[i][4] for i in range(len(chars)) if i not in used)
    return items, leftover


def parse_grammar_tables(doc: fitz.Document) -> dict[str, list[dict[str, object]]]:
    """Structured grammar outline items per level (7 = 七—九级 band)."""
    result: dict[str, list[dict[str, object]]] = {}
    leftover_total = ""
    for level, (p1, p2) in GRAMMAR_LEVEL_PAGES.items():
        items = []
        for pno in range(p1 - 1, p2):
            page_items, leftover = g_extract_page(doc[pno], pno)
            items.extend(page_items)
            leftover_total += leftover
        merged = []
        for it in items:
            key = (it["cat"], it["name"], it["sub"])
            if merged and (merged[-1]["cat"], merged[-1]["name"], merged[-1]["sub"]) == key:
                merged[-1]["content"].extend(it["content"])
            else:
                merged.append(dict(it))
        result[str(level)] = merged
    # Leftovers must be page furniture only: footer page numbers and the
    # per-section title line "HSK（...）语法" that sits above the table.
    furniture = re.sub(r"[HSK（）语法一级二级三级四级五级六级七八九、\d\s\-—]", "", leftover_total)
    if furniture:
        raise ValueError(f"grammar parse left non-furniture chars: {furniture[:60]!r}")
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(OUTLINE_PDF)
    vocab = parse_vocab(doc)
    grammar = parse_grammar(doc)
    grammar_tables = parse_grammar_tables(doc)

    level_counts = {
        str(level): sum(
            1
            for rec in vocab
            if LEVEL_SERIAL_RANGES[level][0] <= int(rec["serial"]) <= LEVEL_SERIAL_RANGES[level][1]
        )
        for level in LEVEL_SERIAL_RANGES
    }
    flags = [rec["serial"] for rec in vocab if rec["flag"]]
    level_problems = check_level_columns(vocab)
    serials = [int(rec["serial"]) for rec in vocab]
    assert serials == list(range(1, FINAL_SERIAL + 1)), "serial continuity broken"
    assert not level_problems, f"level column mismatches: {level_problems[:5]}"
    grammar_counts = {str(k): len(v) for k, v in grammar_tables.items()}
    total_items = sum(grammar_counts.values())
    assert 300 <= total_items <= 340, f"grammar outline item counts {grammar_counts}"

    report = {
        "source_pdf": OUTLINE_PDF.name,
        "source_sha256": sha256(OUTLINE_PDF),
        "parsed_at": datetime.now(UTC).isoformat(),
        "parser": "parse_syllabus.py v2",
        "vocab_rows": len(vocab),
        "vocab_level_counts": level_counts,
        "vocab_flagged_rows": flags,
        "grammar_lines": {level: len(lines) for level, lines in grammar.items()},
        "grammar_items": {level: len(v) for level, v in grammar_tables.items()},
    }
    (OUT_DIR / "vocab_l1_9_draft.json").write_text(
        json.dumps(vocab, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT_DIR / "vocab_l1_4_draft.json").write_text(
        json.dumps([r for r in vocab if int(r["serial"]) <= 2000], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (OUT_DIR / "grammar_outline.json").write_text(
        json.dumps(grammar_tables, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT_DIR / "grammar_draft_l1_4.json").write_text(
        json.dumps({k: v for k, v in grammar.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8"
    )
    (OUT_DIR / "parse_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
