"""Small Japanese text helpers shared by the build and lookup code."""


def kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def hira2kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def is_kanji(c):
    return "一" <= c <= "鿿" or "㐀" <= c <= "䶿"


def is_word_char(c):
    """Kanji, hiragana, katakana or the iteration mark. Used to skip entries with digits, Latin letters, etc."""
    return is_kanji(c) or "ぁ" <= c <= "ゟ" or "゠" <= c <= "ヿ" or c == "々"


def has_katakana(s):
    return any("ァ" <= c <= "ヶ" for c in s)


def kanji_in(text):
    """Unique kanji of `text`, in order of first appearance."""
    return list(dict.fromkeys(c for c in (text or "") if is_kanji(c)))
