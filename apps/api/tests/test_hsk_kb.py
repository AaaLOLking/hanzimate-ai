"""HSK 考纲知识库检索单测：单字/多字/拼音/等级过滤/查无此项/合同字段。"""

from app.realtime.tools import lookup_hsk

CONTRACT_KEYS = {
    "title",
    "document_id",
    "version",
    "level",
    "rights",
    "framework",
    "explanation",
    "examples",
}


def test_single_character_query_hits_vocabulary():
    output = lookup_hsk("把")
    assert output["status"] == "succeeded"
    first = output["sources"][0]
    assert first["kind"] == "vocabulary"
    assert first["title"] == "把"
    assert first["pinyin"] == "bǎ"
    assert first["level"] == "HSK3"


def test_multi_character_word_query():
    output = lookup_hsk("图书馆")
    assert output["status"] == "succeeded"
    assert output["sources"][0]["title"] == "图书馆"
    assert output["sources"][0]["pinyin"] == "túshūguǎn"


def test_pinyin_query_with_tone_mark():
    output = lookup_hsk("bǎ")
    assert output["status"] == "succeeded"
    assert output["sources"][0]["title"] == "把"


def test_pinyin_query_without_tone_mark():
    output = lookup_hsk("ba")
    assert output["status"] == "succeeded"
    titles = [source["title"] for source in output["sources"]]
    assert "吧" in titles


def test_level_filter_restricts_results():
    output = lookup_hsk("HSK2 比较")
    assert output["status"] == "succeeded"
    assert output["sources"]
    for source in output["sources"]:
        assert source["level"].startswith("HSK2")

    chinese = lookup_hsk("二级 比较")
    assert chinese["status"] == "succeeded"
    assert all(s["level"].startswith("HSK2") for s in chinese["sources"])


def test_level_filter_without_match_returns_no_results():
    output = lookup_hsk("HSK1 把字句")
    assert output["status"] == "no_results"
    assert "HSK1" in output["message"]


def test_grammar_point_query():
    output = lookup_hsk("把字句")
    assert output["status"] == "succeeded"
    first = output["sources"][0]
    assert first["kind"] == "grammar"
    assert first["title"] == "把字句"
    assert "HSK3" in first["level"]
    assert "把" in first["explanation"]
    assert first["examples"]


def test_punctuation_insensitive_grammar_query():
    output = lookup_hsk("只有…才…")
    assert output["status"] == "succeeded"
    assert output["sources"][0]["title"] == "只有……才……"


def test_no_match_never_fabricates():
    output = lookup_hsk("zzzxxyy")
    assert output["status"] == "no_results"
    assert output["sources"] == []
    assert "编造" in output["message"]


def test_response_contract_fields():
    output = lookup_hsk("把字句")
    assert output["status"] == "succeeded"
    for source in output["sources"]:
        assert CONTRACT_KEYS <= set(source)
        assert source["version"] == "hsk-kb-v2"
        assert "2025-11" in source["framework"]


def test_band_query_hsk9_hits_level_band_vocabulary():
    output = lookup_hsk("HSK9 成语")
    assert output["status"] == "succeeded"
    assert output["sources"]
    for source in output["sources"]:
        assert source["level"] == "HSK7-9"
        assert source["kind"] == "vocabulary"
        assert "成语" in source["pos"]


def test_band_query_chinese_level_word():
    output = lookup_hsk("九级 成语")
    assert output["status"] == "succeeded"
    assert all(s["level"] == "HSK7-9" for s in output["sources"])


def test_band_query_hsk8_grammar():
    output = lookup_hsk("八级 比较句5")
    assert output["status"] == "succeeded"
    first = output["sources"][0]
    assert first["kind"] == "grammar"
    assert first["level"].startswith("HSK7-9")
    assert first["title"] == "比较句5"


def test_hsk6_vocabulary_query():
    output = lookup_hsk("HSK6 被动句3")
    assert output["status"] == "succeeded"
    assert output["sources"][0]["level"].startswith("HSK6")


def test_band_filter_excludes_lower_levels():
    output = lookup_hsk("HSK9 图书馆")
    assert output["status"] == "no_results"
    assert "HSK9" in output["message"]
