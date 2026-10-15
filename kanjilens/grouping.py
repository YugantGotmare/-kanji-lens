"""Group the common words of one kanji by the reading that kanji has inside each word.

Pure functions, no file or network access, so they are easy to test.
"""
from collections import defaultdict

from .text import has_katakana, hira2kata, kata2hira

WORDS_PER_GROUP = 4      # words kept per reading
SPECIAL_LIMIT = 3        # words kept in the "set words" group (kanji has no reading of its own there)
MAX_GROUPS = 6           # readings kept per kanji (the set-word group is extra)
MIN_SCORE = 3.0          # zipf frequency; 3.0 is about one occurrence per million words
OTHER_MIN_BEST = 3.8     # an unlisted sound-change reading needs a clearly common word to be shown
BARE_KANJI_PENALTY = 1.0  # the kanji alone is common everywhere; rank real compounds above it

_VOICE = {
    "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
    "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
    "た": "だ", "ち": "じぢ", "つ": "ずづ", "て": "で", "と": "ど",
    "は": "ばぱ", "ひ": "びぴ", "ふ": "ぶぷ", "へ": "べぺ", "ほ": "ぼぽ",
}


def reading_variants(r):
    """The base reading plus its sound-change forms (rendaku such as か→が, and sokuon such as く→っ)."""
    out = {r}
    for first in [r[0]] + list(_VOICE.get(r[0], "")):
        v = first + r[1:]
        out.add(v)
        if len(v) > 1 and v[-1] in "くきつち":
            out.add(v[:-1] + "っ")
    return out


def reading_map(on, kun):
    """Maps every surface reading to (base reading, 'on' | 'kun') using KANJIDIC's reading lists."""
    bases = []
    for r in on:
        b = kata2hira(r.replace("-", "").replace(".", ""))
        if b:
            bases.append((b, "on"))
    for r in kun:
        b = kata2hira(r.split(".")[0].replace("-", ""))
        if b:
            bases.append((b, "kun"))
    m = {}
    for b, t in bases:
        m.setdefault(b, (b, t))
    for b, t in bases:
        for v in reading_variants(b):
            m.setdefault(v, (b, t))
    return m


def kun_forms(kun_list, base):
    """Dictionary forms of a kun reading with the okurigana split marked, e.g. 'う·まれる、う·む'."""
    forms = []
    for r in kun_list:
        if kata2hira(r.split(".")[0].replace("-", "")) == base:
            f = r.replace(".", "·").replace("-", "")
            if f not in forms:
                forms.append(f)
    if forms == [base]:
        return ""  # nothing to add to the title
    return "、".join(forms[:3])


def common_readings(jm):
    """word -> set of readings that JMdict itself marks as common. jm maps (written, reading) to
    (gloss, kanji_priority, reading_priority, bad)."""
    out = defaultdict(set)
    for (w, r), (_gloss, _kp, rp, bad) in jm.items():
        if not bad and rp < 100:
            out[w].add(r)
    return out


def build_groups(ch, info, furi_entries, jm, common, zipf_fn):
    """Returns the reading groups of kanji `ch`, best first.

    info          dict with 'on' and 'kun' reading lists (KANJIDIC style)
    furi_entries  list of (word, full_reading, reading_of_this_kanji, covers_several_kanji)
    jm            {(written, reading): (gloss, kanji_priority, reading_priority, bad)}
    common        result of common_readings(jm)
    zipf_fn       word -> zipf frequency or None
    """
    rmap = reading_map(info["on"], info["kun"])
    buckets = defaultdict(list)
    seen = set()
    for text, reading, rd, multi in furi_entries:
        key = (text, reading, rd)
        if key in seen:
            continue
        seen.add(key)
        entry = jm.get((text, reading))
        if not entry:
            continue
        gloss, kp, rp, bad = entry
        if bad:
            continue
        if has_katakana(reading) and not has_katakana(text):
            continue  # katakana spelling of a word written in kanji, e.g. 行く【イク】
        if rp >= 100 and common.get(text):
            continue  # a rare reading of a word that has a common reading
        z = zipf_fn(text)
        score = z if z is not None else (3.2 if min(kp, rp) < 100 else 0.0)
        if score < MIN_SCORE:
            continue
        if text == ch:
            score -= BARE_KANJI_PENALTY
        item = {"word": text, "reading": reading, "gloss": gloss, "score": round(score, 2)}
        if multi:
            buckets[("", "special")].append(item)
        else:
            rd_h = kata2hira(rd)
            base, typ = rmap.get(rd_h, (rd_h, "other"))
            buckets[(base, typ)].append(item)

    groups = []
    for (base, typ), items in buckets.items():
        items.sort(key=lambda x: (-x["score"], x["word"], x["reading"]))
        limit = SPECIAL_LIMIT if typ == "special" else WORDS_PER_GROUP
        kept, seen_meaning = [], set()
        for it in items:
            sig = (it["word"], it["gloss"])
            if sig in seen_meaning:
                continue
            seen_meaning.add(sig)
            kept.append(it)
            if len(kept) >= limit:
                break
        if kept and typ == "other" and kept[0]["score"] < OTHER_MIN_BEST:
            continue
        if kept:
            groups.append({
                "base": base,
                "type": typ,
                "kun_forms": kun_forms(info["kun"], base) if typ == "kun" else "",
                "best": kept[0]["score"],
                "words": kept,
            })
    normal = sorted((g for g in groups if g["type"] != "special"), key=lambda g: (-g["best"], g["base"]))[:MAX_GROUPS]
    special = [g for g in groups if g["type"] == "special"]
    for g in normal + special:
        g.pop("best")
    return normal + special


def group_title(g):
    """Display title of a group: katakana for on'yomi, hiragana for kun'yomi."""
    if g["type"] == "on":
        return hira2kata(g["base"])
    if g["type"] == "special":
        return "Set words"
    return g["base"]
