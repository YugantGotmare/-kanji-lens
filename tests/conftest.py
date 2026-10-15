"""Synthetic raw data in the real file formats, so the whole build can be tested without any download."""
import bz2
import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KANJIDIC = """<?xml version="1.0" encoding="UTF-8"?>
<kanjidic2>
<character><literal>犬</literal><misc><grade>1</grade><stroke_count>4</stroke_count><freq>1326</freq><jlpt>3</jlpt></misc>
<reading_meaning><rmgroup><reading r_type="ja_on">ケン</reading><reading r_type="ja_kun">いぬ</reading><reading r_type="ja_kun">いぬ-</reading><reading r_type="pinyin">quan3</reading><meaning>dog</meaning><meaning m_lang="fr">chien</meaning></rmgroup></reading_meaning></character>
<character><literal>生</literal><misc><grade>1</grade><stroke_count>5</stroke_count><freq>29</freq><jlpt>4</jlpt></misc>
<reading_meaning><rmgroup><reading r_type="ja_on">セイ</reading><reading r_type="ja_on">ショウ</reading><reading r_type="ja_kun">い.きる</reading><reading r_type="ja_kun">う.まれる</reading><reading r_type="ja_kun">なま</reading><meaning>life</meaning><meaning>birth</meaning></rmgroup></reading_meaning></character>
<character><literal>鬱</literal><misc><grade>9</grade><stroke_count>29</stroke_count></misc>
<reading_meaning><rmgroup><reading r_type="ja_on">ウツ</reading><meaning>depression</meaning></rmgroup></reading_meaning></character>
</kanjidic2>"""

JMDICT = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE JMdict [
<!ELEMENT JMdict (entry*)>
<!ENTITY oK "word containing out-dated kanji or kanji usage">
<!ENTITY X "rude or X-rated term (not displayed in educational software)">
<!ENTITY n "noun (common) (futsuumeishi)">
]>
<JMdict>
<entry><ent_seq>1</ent_seq><k_ele><keb>犬</keb><ke_pri>ichi1</ke_pri><ke_pri>nf08</ke_pri></k_ele><r_ele><reb>いぬ</reb><re_pri>ichi1</re_pri></r_ele><sense><gloss>dog</gloss><gloss>canine</gloss></sense></entry>
<entry><ent_seq>2</ent_seq><k_ele><keb>子犬</keb><ke_pri>nf20</ke_pri></k_ele><r_ele><reb>こいぬ</reb><re_pri>nf20</re_pri></r_ele><sense><gloss>puppy</gloss></sense></entry>
<entry><ent_seq>3</ent_seq><k_ele><keb>愛犬</keb><ke_pri>news2</ke_pri></k_ele><r_ele><reb>あいけん</reb><re_pri>news2</re_pri></r_ele><sense><gloss>pet dog</gloss></sense></entry>
<entry><ent_seq>4</ent_seq><k_ele><keb>犬猿の仲</keb><ke_pri>nf40</ke_pri></k_ele><r_ele><reb>けんえんのなか</reb><re_pri>nf40</re_pri></r_ele><sense><gloss>like cats and dogs</gloss></sense></entry>
<entry><ent_seq>5</ent_seq><k_ele><keb>柴犬</keb><ke_pri>nf30</ke_pri></k_ele><r_ele><reb>しばいぬ</reb><re_pri>nf30</re_pri></r_ele><sense><gloss>shiba inu</gloss></sense></entry>
<entry><ent_seq>6</ent_seq><k_ele><keb>狂犬病</keb></k_ele><r_ele><reb>きょうけんびょう</reb></r_ele><sense><gloss>rabies</gloss></sense></entry>
<entry><ent_seq>7</ent_seq><k_ele><keb>学生</keb><ke_pri>ichi1</ke_pri><ke_pri>nf01</ke_pri></k_ele><k_ele><keb>學生</keb><ke_inf>&oK;</ke_inf></k_ele><r_ele><reb>がくせい</reb><re_pri>ichi1</re_pri><re_pri>nf01</re_pri></r_ele><r_ele><reb>がくしょう</reb></r_ele><sense><pos>&n;</pos><gloss>student</gloss></sense></entry>
<entry><ent_seq>8</ent_seq><k_ele><keb>生活</keb><ke_pri>ichi1</ke_pri><ke_pri>nf01</ke_pri></k_ele><r_ele><reb>せいかつ</reb><re_pri>ichi1</re_pri></r_ele><sense><gloss>life; living</gloss></sense></entry>
<entry><ent_seq>9</ent_seq><k_ele><keb>先生</keb><ke_pri>ichi1</ke_pri><ke_pri>nf02</ke_pri></k_ele><r_ele><reb>せんせい</reb><re_pri>ichi1</re_pri></r_ele><sense><gloss>teacher</gloss></sense></entry>
<entry><ent_seq>10</ent_seq><k_ele><keb>生まれる</keb><ke_pri>ichi1</ke_pri></k_ele><r_ele><reb>うまれる</reb><re_pri>ichi1</re_pri></r_ele><sense><gloss>to be born</gloss></sense></entry>
<entry><ent_seq>11</ent_seq><k_ele><keb>弥生</keb><ke_pri>nf40</ke_pri></k_ele><r_ele><reb>やよい</reb><re_pri>nf40</re_pri></r_ele><sense><gloss>March (lunar calendar)</gloss></sense></entry>
<entry><ent_seq>12</ent_seq><k_ele><keb>生</keb><ke_pri>ichi1</ke_pri></k_ele><r_ele><reb>なま</reb><re_pri>ichi1</re_pri></r_ele><r_ele><reb>き</reb></r_ele><sense><gloss>raw; draft</gloss></sense><sense><misc>&X;</misc><gloss>rude sense</gloss></sense></entry>
<entry><ent_seq>13</ent_seq><r_ele><reb>ありがとう</reb></r_ele><sense><gloss>thanks</gloss></sense></entry>
</JMdict>"""

FURIGANA = """犬|いぬ|0:いぬ
子犬|こいぬ|0:こ;1:いぬ
愛犬|あいけん|0:あい;1:けん
犬猿の仲|けんえんのなか|0:けん;1:えん;3:なか
柴犬|しばいぬ|0:しば;1:いぬ
狂犬病|きょうけんびょう|0:きょう;1:けん;2:びょう
学生|がくせい|0:がく;1:せい
學生|がくせい|0:がく;1:せい
学生|がくしょう|0:がく;1:しょう
生活|せいかつ|0:せい;1:かつ
先生|せんせい|0:せん;1:せい
生まれる|うまれる|0:う
生|なま|0:なま
生|き|0:き
弥生|やよい|0-1:やよい
"""

JPN = [
    (1, "隣の犬はほえてばかりいます。"),
    (2, "子犬は日に日に大きくなった。"),
    (3, "愛犬の病気は重かった。"),
    (4, "先生は学生に本を貸した。"),
    (5, "犬。"),
    (6, "赤ちゃんが生まれた。"),
    (7, "生活は楽ではない。"),
    (8, "彼は犬が好きです。"),
]
ENG = {
    101: "The dog next door is always barking.",
    102: "The puppy grew larger every day.",
    103: "My pet dog was seriously ill.",
    104: "The teacher lent the student a book.",
    105: "Dog.",
    106: "A baby was born.",
    107: "Life is not easy.",
    108: "He likes dogs.",
}

ZIPF = {"犬": 5.1, "子犬": 3.9, "愛犬": 3.6, "犬猿の仲": 3.2, "柴犬": 3.7, "狂犬病": 2.4, "学生": 5.0,
        "生活": 5.3, "先生": 5.3, "生まれる": 4.4, "弥生": 3.6, "生": 5.5}


def write_bz2(path, rows):
    with bz2.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")


@pytest.fixture(scope="session")
def raw(tmp_path_factory):
    d = tmp_path_factory.mktemp("raw")
    with gzip.open(d / "kanjidic2.xml.gz", "wb") as f:
        f.write(KANJIDIC.encode())
    with gzip.open(d / "JMdict_e.gz", "wb") as f:
        f.write(JMDICT.encode())
    (d / "JmdictFurigana.txt").write_text("﻿" + FURIGANA, encoding="utf-8")
    write_bz2(d / "jpn_sentences.tsv.bz2", [(i, "jpn", t) for i, t in JPN])
    write_bz2(d / "eng_sentences.tsv.bz2", [(i, "eng", t) for i, t in ENG.items()])
    write_bz2(d / "jpn-eng_links.tsv.bz2", [(i, i + 100) for i, _ in JPN])
    return d


@pytest.fixture(scope="session")
def zipf():
    return ZIPF.get


@pytest.fixture(scope="session")
def db_path(raw, zipf, tmp_path_factory):
    from kanjilens.builddb import build_database
    from kanjilens.sources import read_tatoeba

    out = tmp_path_factory.mktemp("db") / "kanji_lens.db"
    sentences = read_tatoeba(raw / "jpn_sentences.tsv.bz2", raw / "eng_sentences.tsv.bz2", raw / "jpn-eng_links.tsv.bz2")
    build_database(str(out), str(raw / "kanjidic2.xml.gz"), str(raw / "JMdict_e.gz"), str(raw / "JmdictFurigana.txt"),
                   zipf, sentences=sentences, log=lambda *_: None)
    return out
