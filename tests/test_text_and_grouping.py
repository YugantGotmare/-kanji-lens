from kanjilens.grouping import build_groups, common_readings, reading_map, reading_variants
from kanjilens.text import has_katakana, hira2kata, is_kanji, kanji_in, kata2hira


def test_kana_conversion_roundtrip():
    assert kata2hira("ケンエン") == "けんえん"
    assert hira2kata("いぬ") == "イヌ"
    assert kata2hira("ー") == "ー"  # the long-vowel mark is not changed


def test_kanji_detection():
    assert is_kanji("犬") and not is_kanji("い") and not is_kanji("A") and not is_kanji("３")
    assert kanji_in("犬と大と犬") == ["犬", "大"]
    assert kanji_in("") == [] and kanji_in(None) == []
    assert has_katakana("イク") and not has_katakana("いく")


def test_sound_changes_are_recognised():
    v = reading_variants("かく")
    assert {"かく", "がく", "かっ", "がっ"} <= v
    m = reading_map(["ガク"], [])
    assert m["がく"] == ("がく", "on")
    m = reading_map(["コウ"], ["おこな.う", "い.く"])
    assert m["ごう"] == ("こう", "on")   # rendaku
    assert m["おこな"] == ("おこな", "kun")
    assert reading_map(["ガク"], [])["がっ"] == ("がく", "on")  # sokuon, as in 学校【がっこう】


def _info(on, kun):
    return {"on": on, "kun": kun}


def test_groups_split_by_reading_and_filter_noise():
    furi = [
        ("学生", "がくせい", "せい", False),
        ("学生", "がくしょう", "しょう", False),  # rare reading of a word with a common reading
        ("學生", "がくせい", "せい", False),      # outdated spelling
        ("先生", "せんせい", "せい", False),
        ("生まれる", "うまれる", "う", False),
        ("弥生", "やよい", "やよい", True),
        ("生", "いく", "いく", False),             # unlisted, rare reading of a spelling that has a common one
        ("生", "なま", "なま", False),
        ("行く", "イク", "い", False),             # katakana reading of a kanji word
    ]
    jm = {
        ("学生", "がくせい"): ("student", 1, 1, 0),
        ("学生", "がくしょう"): ("student", 1, 100, 0),
        ("學生", "がくせい"): ("student", 100, 1, 1),
        ("先生", "せんせい"): ("teacher", 2, 2, 0),
        ("生まれる", "うまれる"): ("to be born", 60, 60, 0),
        ("弥生", "やよい"): ("March", 40, 40, 0),
        ("生", "いく"): ("life", 100, 100, 0),
        ("生", "なま"): ("raw", 60, 60, 0),
        ("行く", "イク"): ("to go", 60, 100, 0),
    }
    z = {"学生": 5.0, "先生": 5.3, "生まれる": 4.4, "弥生": 3.6, "生": 5.5, "行く": 5.5}.get
    groups = build_groups("生", _info(["セイ", "ショウ"], ["い.きる", "う.まれる"]), furi, jm, common_readings(jm), z)
    by = {(g["type"], g["base"]): [w["word"] for w in g["words"]] for g in groups}
    assert by[("on", "せい")] == ["先生", "学生"]       # best word first, outdated spelling and rare reading dropped
    assert by[("kun", "う")] == ["生まれる"]
    assert by[("special", "")] == ["弥生"]
    assert not any(g["base"] == "いく" for g in groups)  # weak unlisted reading hidden
    assert all("行く" not in [w["word"] for w in g["words"]] for g in groups)
    assert groups[-1]["type"] == "special"               # set words always last
    # the kun group carries the display form with the okurigana split marked
    kun = next(g for g in groups if g["base"] == "う")
    assert kun["kun_forms"] == "う·まれる"


def test_limits_per_group():
    furi = [("犬" + c, "けん", "けん", False) for c in "あいうえおかき"]
    jm = {("犬" + c, "けん"): (f"g{c}", 1, 1, 0) for c in "あいうえおかき"}
    groups = build_groups("犬", _info(["ケン"], []), furi, jm, common_readings(jm), lambda w: 4.0)
    assert len(groups) == 1 and len(groups[0]["words"]) == 4  # WORDS_PER_GROUP
