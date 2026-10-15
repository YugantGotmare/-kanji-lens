import os
import sqlite3
from pathlib import Path

import pytest

from kanjilens.lookup import KanjiDB, format_text
from kanjilens.sentences import SentenceIndex
from kanjilens.sources import parse_furigana, parse_jmdict, parse_kanjidic


def test_parsers(raw):
    kd = {k["literal"]: k for k in parse_kanjidic(raw / "kanjidic2.xml.gz")}
    assert kd["犬"]["on"] == ["ケン"] and kd["犬"]["kun"] == ["いぬ", "いぬ-"]
    assert kd["犬"]["meanings"] == ["dog"] and kd["犬"]["grade"] == 1 and kd["犬"]["freq"] == 1326

    rows = list(parse_jmdict(raw / "JMdict_e.gz"))
    by = {(r[0], r[1]): r for r in rows}
    assert by[("犬", "いぬ")][2] == "dog; canine"
    assert by[("學生", "がくせい")][5] == 1            # outdated kanji spelling is flagged
    assert by[("生", "なま")][2] == "raw; draft"        # the vulgar sense is dropped
    assert not any(r[0] == "ありがとう" for r in rows)   # entries without kanji are ignored

    furi = parse_furigana(raw / "JmdictFurigana.txt")  # file starts with a BOM, like the real one
    assert ("子犬", "こいぬ", "いぬ", False) in furi["犬"]
    assert ("弥生", "やよい", "やよい", True) in furi["弥"]


def test_sentence_index_checks_the_reading(raw):
    idx = SentenceIndex([(1, "先生は学生に本を貸した。", "x"), (2, "彼は人気がある。", "y"),
                         (3, "赤ちゃんが生まれた。", "z"), (4, "子犬は大きい。", "w")], log=lambda *_: None)
    assert [s["id"] for s in idx.find("先生", "せんせい")] == [1]
    assert [s["id"] for s in idx.find("人気", "にんき")] == [2]
    assert idx.find("人気", "ひとけ") == []                 # same spelling, different reading: not matched
    assert [s["id"] for s in idx.find("生まれる", "うまれる")] == [3]  # inflected form matches the dictionary form
    assert [s["id"] for s in idx.find("子犬", "こいぬ")] == [4]       # compound split by the tokenizer
    assert idx.find("先生", "せんせい", used={1}) == []


def test_database_contents(db_path):
    db = KanjiDB(str(db_path))
    meta = db.meta()
    assert meta["count_kanji"] == "2"   # 犬 and 生; 鬱 (grade 9, no frequency rank) is left out
    assert db.known("犬") and not db.known("鬱")
    assert db.get("鬱") is None and db.get("a") is None


def test_dog(db_path):
    e = KanjiDB(str(db_path)).get("犬")
    assert e["meanings"] == "dog" and e["strokes"] == 4 and e["on"] == ["ケン"]
    g = {(x["type"], x["base"]): x for x in e["groups"]}
    # the plain word comes first; the bare-kanji penalty only matters when a compound is nearly as common
    assert [w["word"] for w in g[("kun", "いぬ")]["words"]] == ["犬", "子犬", "柴犬"]
    assert g[("kun", "いぬ")]["kun_forms"] == ""          # いぬ and いぬ- add nothing beyond the title
    assert [w["word"] for w in g[("on", "けん")]["words"]] == ["愛犬", "犬猿の仲"]
    assert g[("on", "けん")]["title"] == "ケン"
    everything = [w["word"] for x in e["groups"] for w in x["words"]]
    assert "狂犬病" not in everything                      # too rare, no priority tag
    dog, puppy, shiba = g[("kun", "いぬ")]["words"]
    assert dog["sentences"][0]["jp"] == "隣の犬はほえてばかりいます。"
    assert puppy["sentences"][0]["jp"] == "子犬は日に日に大きくなった。"
    assert puppy["sentences"][0]["id"] == 2                # Tatoeba id kept for the required credit
    assert puppy["sentences"][0]["en"] == "The puppy grew larger every day."
    # 柴犬 has no matching sentence, and none is invented
    assert shiba["sentences"] == []
    # a sentence is never reused for a second word of the same kanji
    ids = [s["id"] for x in e["groups"] for w in x["words"] for s in w["sentences"]]
    assert len(ids) == len(set(ids))


def test_life(db_path):
    e = KanjiDB(str(db_path)).get("生")
    g = {(x["type"], x["base"]): [w["word"] for w in x["words"]] for x in e["groups"]}
    assert g[("on", "せい")] == ["先生", "生活", "学生"]
    assert g[("kun", "う")] == ["生まれる"]
    assert g[("kun", "なま")] == ["生"]
    assert g[("special", "")] == ["弥生"]
    assert ("kun", "き") not in g                           # reading with no priority anywhere is hidden
    words = [w["word"] + w["reading"] for x in e["groups"] for w in x["words"]]
    assert "學生がくせい" not in words and "学生がくしょう" not in words


def test_text_lookup_and_formatting(db_path):
    db = KanjiDB(str(db_path))
    entries = db.get_many("犬と鬱と生き物と犬")
    assert [x["literal"] for x in entries] == ["犬", "生"]  # unknown kanji skipped, duplicates removed
    out = format_text(entries[0])
    assert "子犬【こいぬ】 puppy" in out and "[on] ケン" in out


def test_database_is_read_only(db_path):
    db = KanjiDB(str(db_path))
    with pytest.raises(sqlite3.OperationalError):
        db.con.execute("DELETE FROM kanji")


# --- optional: the real JmdictFurigana file, if present --------------------------------------------------
REAL = os.environ.get("KANJILENS_FURIGANA")


@pytest.mark.skipif(not REAL or not Path(REAL).exists(), reason="set KANJILENS_FURIGANA to the real file")
def test_real_furigana_file_parses():
    furi = parse_furigana(REAL)
    assert len(furi) > 3000
    assert any(w == "先生" and r == "せんせい" for w, r, _rd, _m in furi["生"])
    assert any(w == "弥生" and m for w, _r, _rd, m in furi["弥"])
