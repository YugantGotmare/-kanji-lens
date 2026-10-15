"""Build the ready-made SQLite database that the app ships with.

Everything slow (downloading, ranking, grouping, sentence checking) happens here, once. The running app only
reads the finished file.
"""
import json
import math
import os
import sqlite3
import time
from collections import defaultdict

from .grouping import build_groups, common_readings
from .sentences import SentenceIndex
from .sources import parse_furigana, parse_jmdict, parse_kanjidic

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE kanji(
    literal TEXT PRIMARY KEY, grade INTEGER, jlpt INTEGER, strokes INTEGER, freq INTEGER,
    meanings TEXT, on_json TEXT, kun_json TEXT);
CREATE TABLE groups(
    id INTEGER PRIMARY KEY, literal TEXT NOT NULL, pos INTEGER NOT NULL,
    base TEXT, type TEXT, kun_forms TEXT);
CREATE TABLE words(
    id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL, pos INTEGER NOT NULL,
    word TEXT, reading TEXT, gloss TEXT, score REAL);
CREATE TABLE sentences(
    word_id INTEGER NOT NULL, pos INTEGER NOT NULL, tatoeba_id INTEGER, jp TEXT, en TEXT);
CREATE INDEX idx_groups_literal ON groups(literal);
CREATE INDEX idx_words_group ON words(group_id);
CREATE INDEX idx_sentences_word ON sentences(word_id);
"""


def select_kanji(info):
    """Kanji worth including: school and general-use grades (1-8) or anything in KANJIDIC's top-2500 list."""
    return (info["grade"] is not None and 1 <= info["grade"] <= 8) or info["freq"] is not None


def wordfreq_zipf():
    """Zipf frequency function backed by the wordfreq package (about 1 = rare, 7 = most common)."""
    from wordfreq import get_frequency_dict

    d = get_frequency_dict("ja")

    def zipf(word):
        f = d.get(word)
        return math.log10(f) + 9 if f else None

    return zipf


def build_database(out_path, kanjidic_path, jmdict_path, furigana_path, zipf_fn,
                   sentences=None, limit=None, sentences_per_word=2, log=print):
    t0 = time.time()
    log("reading KANJIDIC2 ...")
    infos = {}
    for info in parse_kanjidic(kanjidic_path):
        if select_kanji(info):
            infos[info["literal"]] = info
    log(f"  {len(infos)} kanji selected")

    log("reading JMdict (about 1-2 minutes) ...")
    jm = {}
    for keb, reb, gloss, kp, rp, bad in parse_jmdict(jmdict_path):
        key = (keb, reb)
        cur = jm.get(key)
        if cur is None or bad < cur[3] or (bad == cur[3] and min(kp, rp) < min(cur[1], cur[2])):
            jm[key] = (gloss, kp, rp, bad)
    common = common_readings(jm)
    meanings_by_spelling = defaultdict(set)
    for (spelling, _reading), (gloss, _kp, _rp, bad) in jm.items():
        if not bad:
            meanings_by_spelling[spelling].add(gloss)
    ambiguous = {w for w, meanings in meanings_by_spelling.items() if len(meanings) > 1}
    log(f"  {len(jm)} word/reading pairs")

    log("reading JmdictFurigana ...")
    furi = parse_furigana(furigana_path)

    index = None
    if sentences:
        log("tokenizing example sentences (a few minutes) ...")
        index = SentenceIndex(sentences, log=log)

    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    counts = {"kanji": 0, "groups": 0, "words": 0, "sentences": 0}
    literals = sorted(infos, key=lambda c: (infos[c]["freq"] or 99999, c))
    if limit:
        literals = literals[:limit]
    gid = wid = 0
    for ch in literals:
        info = infos[ch]
        groups = build_groups(ch, info, furi.get(ch, []), jm, common, zipf_fn)
        con.execute(
            "INSERT INTO kanji VALUES (?,?,?,?,?,?,?,?)",
            (ch, info["grade"], info["jlpt"], info["strokes"], info["freq"], "; ".join(info["meanings"]),
             json.dumps(info["on"], ensure_ascii=False), json.dumps(info["kun"], ensure_ascii=False)),
        )
        counts["kanji"] += 1
        used = set()
        for gpos, g in enumerate(groups):
            gid += 1
            con.execute("INSERT INTO groups VALUES (?,?,?,?,?,?)",
                        (gid, ch, gpos, g["base"], g["type"], g["kun_forms"]))
            counts["groups"] += 1
            for wpos, w in enumerate(g["words"]):
                wid += 1
                con.execute("INSERT INTO words VALUES (?,?,?,?,?,?,?)",
                            (wid, gid, wpos, w["word"], w["reading"], w["gloss"], w["score"]))
                counts["words"] += 1
                # A tokenizer cannot validate which dictionary sense was intended.
                # Withhold automatic examples for spellings with distinct meanings.
                if index and w["word"] not in ambiguous and g["type"] != "special":
                    for spos, s in enumerate(index.find(w["word"], w["reading"], used, sentences_per_word)):
                        used.add(s["id"])
                        con.execute("INSERT INTO sentences VALUES (?,?,?,?,?)", (wid, spos, s["id"], s["jp"], s["en"]))
                        counts["sentences"] += 1
        if counts["kanji"] % 500 == 0:
            log(f"  {counts['kanji']} kanji done")

    for k, v in counts.items():
        con.execute("INSERT INTO meta VALUES (?,?)", (f"count_{k}", str(v)))
    con.execute("INSERT INTO meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    con.execute("INSERT INTO meta VALUES ('data_version', '2')")
    con.execute("INSERT INTO meta VALUES ('example_validation', 'tokenizer; sense not reviewed')")
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out_path)
    log(f"built {out_path} in {time.time() - t0:.0f}s: {counts}")
    return counts
