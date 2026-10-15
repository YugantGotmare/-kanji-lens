"""Download and parse the raw data sources.

KANJIDIC2 and JMdict   EDRDG, CC BY-SA 4.0   https://www.edrdg.org
JmdictFurigana         Doublevil             https://github.com/Doublevil/JmdictFurigana
Tatoeba sentences      CC BY 2.0 FR          https://tatoeba.org
"""
import bz2
import gzip
import os
import time
import urllib.request
from collections import defaultdict

from lxml import etree

from .text import is_kanji, is_word_char

URLS = {
    "kanjidic2.xml.gz": [
        "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz",
        "http://www.edrdg.org/kanjidic/kanjidic2.xml.gz",
    ],
    "JMdict_e.gz": [
        "https://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz",
        "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz",
    ],
    "JmdictFurigana.txt": [
        "https://github.com/Doublevil/JmdictFurigana/releases/latest/download/JmdictFurigana.txt",
    ],
    "jpn_sentences.tsv.bz2": ["https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2"],
    "eng_sentences.tsv.bz2": ["https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2"],
    "jpn-eng_links.tsv.bz2": ["https://downloads.tatoeba.org/exports/per_language/jpn/jpn-eng_links.tsv.bz2"],
}

# JMdict tags that mark a spelling as not worth teaching
BAD_KANJI_INFO = ("irregular", "out-dated", "rarely", "search-only")
SKIP_SENSE_MISC = ("X-rated", "vulgar")


def fetch(name, data_dir, urls=None, required=True, log=print):
    """Download `name` into data_dir once. Returns the path, or None if optional and unavailable."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    last = None
    for url in urls or URLS[name]:
        for _ in range(3):
            try:
                log(f"downloading {name} ...")
                req = urllib.request.Request(url, headers={"User-Agent": "kanji-lens/0.1"})
                with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                os.replace(path + ".part", path)
                return path
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
    if required:
        raise RuntimeError(f"Could not download {name}: {last}")
    log(f"WARNING: could not download {name}: {last}")
    return None


def pri_score(tags):
    """JMdict priority tags to a number, lower = more common. 100 means no priority tag."""
    if not tags:
        return 100
    best = 100
    for t in tags:
        if t.startswith("nf") and t[2:].isdigit():
            best = min(best, int(t[2:]))
        elif t in ("news1", "ichi1", "spec1", "gai1"):
            best = min(best, 60)
        else:
            best = min(best, 80)
    return best


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def parse_kanjidic(path):
    """Yields one dict per kanji: literal, grade, jlpt, strokes, freq, meanings, on, kun."""
    with gzip.open(path, "rb") as f:
        for _, el in etree.iterparse(f, events=("end",), tag="character", load_dtd=True):
            misc = el.find("misc")
            g = (lambda t: misc.findtext(t)) if misc is not None else (lambda t: None)
            on, kun = [], []
            for r in el.iterfind(".//reading"):
                rt = r.get("r_type")
                if rt == "ja_on":
                    on.append(r.text)
                elif rt == "ja_kun":
                    kun.append(r.text)
            yield {
                "literal": el.findtext("literal"),
                "grade": _int(g("grade")),
                "jlpt": _int(g("jlpt")),
                "strokes": _int(g("stroke_count")),
                "freq": _int(g("freq")),
                "meanings": [m.text for m in el.iterfind(".//meaning") if m.get("m_lang") is None],
                "on": on,
                "kun": kun,
            }
            el.clear()


def parse_jmdict(path):
    """Yields (written, reading, gloss, kanji_priority, reading_priority, bad) for every kanji spelling."""
    with gzip.open(path, "rb") as f:
        for _, el in etree.iterparse(
            f, events=("end",), tag="entry", load_dtd=True, resolve_entities=True, huge_tree=True
        ):
            senses = []
            for sense in el.iterfind("sense"):
                misc = [x.text or "" for x in sense.iterfind("misc")]
                if any(k in t for t in misc for k in SKIP_SENSE_MISC):
                    continue
                senses.append((
                    [x.text for x in sense.iterfind("stagk")],
                    [x.text for x in sense.iterfind("stagr")],
                    [x.text for x in sense.iterfind("gloss") if x.text
                     and x.get("{http://www.w3.org/XML/1998/namespace}lang", "eng") == "eng"],
                ))
            readings = [
                (
                    r.findtext("reb"),
                    [x.text for x in r.iterfind("re_restr")],
                    pri_score([x.text for x in r.iterfind("re_pri")]),
                )
                for r in el.iterfind("r_ele")
            ]
            for k in el.iterfind("k_ele"):
                keb = k.findtext("keb")
                if not keb or not any(is_kanji(c) for c in keb):
                    continue
                kpri = pri_score([x.text for x in k.iterfind("ke_pri")])
                inf = [x.text or "" for x in k.iterfind("ke_inf")]
                bad_spelling = any(b in t for t in inf for b in BAD_KANJI_INFO)
                for reb, restr, rpri in readings:
                    if restr and keb not in restr:
                        continue
                    glosses = [g for ks, rs, gs in senses
                               if (not ks or keb in ks) and (not rs or reb in rs) for g in gs]
                    gloss = "; ".join(dict.fromkeys(glosses[:4]))
                    bad = int(not gloss or bad_spelling)
                    yield keb, reb, gloss, kpri, rpri, bad
            el.clear()


def parse_furigana(path):
    """kanji -> [(word, full_reading, reading_of_this_kanji, covers_several_kanji)]."""
    idx = defaultdict(list)
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) != 3:
                continue
            text, reading, segs = parts
            if not text or not all(is_word_char(c) for c in text):
                continue
            for seg in segs.split(";"):
                if ":" not in seg:
                    continue
                rng, rd = seg.split(":", 1)
                a, _, b = rng.partition("-")
                a = _int(a)
                b = _int(b) if b else a
                if a is None or b is None:
                    continue
                multi = b > a
                for i in range(a, b + 1):
                    if i < len(text) and is_kanji(text[i]):
                        idx[text[i]].append((text, reading, rd, multi))
    return idx


def _tsv_bz2(path):
    with bz2.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line.rstrip("\n").split("\t")


def read_tatoeba(jpn_path, eng_path, links_path, min_len=5, max_len=40):
    """Japanese sentences that have an English translation: list of (tatoeba_id, japanese, english)."""
    jp = {}
    for p in _tsv_bz2(jpn_path):
        if len(p) >= 3 and min_len <= len(p[2]) <= max_len:
            jp[p[0]] = p[2]
    pairs = {}
    for p in _tsv_bz2(links_path):
        if len(p) >= 2 and p[0] in jp and p[0] not in pairs:
            pairs[p[0]] = p[1]
    wanted = set(pairs.values())
    eng = {}
    for p in _tsv_bz2(eng_path):
        if len(p) >= 3 and p[0] in wanted:
            eng[p[0]] = p[2]
    return [(int(j), jp[j], eng[e]) for j, e in pairs.items() if e in eng]
