"""Read access to the finished database. This is all the running app needs."""
import json
import sqlite3
import sys

from .grouping import group_title
from .text import kanji_in


class KanjiDB:
    def __init__(self, path):
        # read-only, and shareable between the threads of a web server
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    def close(self):
        self.con.close()

    def meta(self):
        return {r["key"]: r["value"] for r in self.con.execute("SELECT key, value FROM meta")}

    def known(self, ch):
        return self.con.execute("SELECT 1 FROM kanji WHERE literal=?", (ch,)).fetchone() is not None

    def get(self, ch):
        """Everything shown for one kanji, or None if it is not in the database."""
        k = self.con.execute("SELECT * FROM kanji WHERE literal=?", (ch,)).fetchone()
        if k is None:
            return None
        groups = []
        for g in self.con.execute("SELECT * FROM groups WHERE literal=? ORDER BY pos", (ch,)):
            words = []
            for w in self.con.execute("SELECT * FROM words WHERE group_id=? ORDER BY pos", (g["id"],)):
                sents = [
                    {"id": s["tatoeba_id"], "jp": s["jp"], "en": s["en"],
                     "verification": "automatic"}
                    for s in self.con.execute("SELECT * FROM sentences WHERE word_id=? ORDER BY pos", (w["id"],))
                ]
                words.append({"word": w["word"], "reading": w["reading"], "gloss": w["gloss"],
                              "score": w["score"], "sentences": sents})
            d = {"base": g["base"], "type": g["type"], "kun_forms": g["kun_forms"], "words": words}
            d["title"] = group_title(d)
            groups.append(d)
        return {
            "literal": k["literal"], "grade": k["grade"], "jlpt": k["jlpt"], "strokes": k["strokes"],
            "freq": k["freq"], "meanings": k["meanings"],
            "on": json.loads(k["on_json"]), "kun": json.loads(k["kun_json"]),
            "groups": groups,
        }

    def get_many(self, text, limit=5):
        """Entries for the kanji found in `text` (first `limit` unique ones), skipping unknown kanji."""
        if limit <= 0:
            return []
        out = []
        for ch in kanji_in(text):
            entry = self.get(ch)
            if entry:
                out.append(entry)
                if len(out) >= limit:
                    break
        return out


def format_text(entry):
    """Plain-text rendering, used by the command line and tests."""
    lines = [f"{entry['literal']}  {entry['meanings']}",
             f"  strokes {entry['strokes']} · grade {entry['grade']} · JLPT(old) {entry['jlpt']} · rank {entry['freq']}",
             f"  音読み {'、'.join(entry['on']) or '-'}",
             f"  訓読み {'、'.join(r.replace('.', '·') for r in entry['kun'][:8]) or '-'}"]
    for g in entry["groups"]:
        sub = g["kun_forms"] if g["kun_forms"] else ""
        lines.append(f"\n  [{g['type']}] {g['title']} {sub}")
        for w in g["words"]:
            lines.append(f"    {w['word']}【{w['reading']}】 {w['gloss']}")
            for s in w["sentences"]:
                lines.append(f"        {s['jp']}  /  {s['en']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python -m kanjilens.lookup kanji_lens.db 犬 [more kanji]")
        sys.exit(1)
    db = KanjiDB(sys.argv[1])
    for entry in db.get_many("".join(sys.argv[2:])):
        print(format_text(entry), "\n")
