"""Index example sentences by (word, reading) so that only sentences where the word is really read that way
are shown. Every sentence is tokenized once, at build time."""
from collections import defaultdict

from .text import hira2kata


class SentenceIndex:
    def __init__(self, sentences, log=print):
        """sentences: iterable of (id, japanese, english)."""
        try:
            import fugashi
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install fugashi unidic-lite") from e
        tagger = fugashi.Tagger()
        self.sentences = {}
        self.index = defaultdict(list)
        n = 0
        for sid, jp, en in sentences:
            self.sentences[sid] = (jp, en)
            for key in self._keys(tagger, jp):
                self.index[key].append(sid)
            n += 1
            if n % 50000 == 0:
                log(f"  tokenized {n} sentences")

    @staticmethod
    def _keys(tagger, jp):
        toks = list(tagger(jp))
        keys = set()
        for i, tok in enumerate(toks):
            f = tok.feature
            # lForm is the lemma's reading: e.g. 行く can have オコナウ there.
            # kanaBase belongs to this orthographic dictionary form instead.
            base, reading = getattr(f, "orthBase", None), getattr(f, "kanaBase", None)
            proper = getattr(f, "pos2", "") == "固有名詞"
            # Contracted -tta/-tte forms can be identical across different verbs
            # (行う and 行く -> 行った). The tokenizer can choose either lemma.
            # Withhold these automatic lemma matches rather than teach a guess.
            ambiguous_inflection = tok.surface.endswith("っ") or (
                tok.surface.endswith(("った", "って")) and tok.surface != base)
            if base and reading and not proper and not ambiguous_inflection:
                keys.add((base, reading))
            # compounds the tokenizer splits into pieces, e.g. 子+犬 read コ+イヌ
            surf, lf = "", ""
            for j in range(i, min(i + 4, len(toks))):
                feature = toks[j].feature
                if getattr(feature, "pos2", "") == "固有名詞":
                    break
                kana = getattr(feature, "kana", None)
                if not kana:
                    break
                surf += toks[j].surface
                lf += kana
                if j > i:
                    keys.add((surf, lf))
        return keys

    def find(self, word, reading, used=(), n=2, target_len=14):
        """Up to n sentences containing `word` read as `reading`, best first (closest to a comfortable length)."""
        ids = [i for i in self.index.get((word, hira2kata(reading)), []) if i not in used]
        ids.sort(key=lambda i: (abs(len(self.sentences[i][0]) - target_len), i))
        return [{"id": i, "jp": self.sentences[i][0], "en": self.sentences[i][1]} for i in ids[:n]]
