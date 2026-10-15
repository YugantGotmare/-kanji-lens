import gzip
import json
from io import BytesIO

from app import make_handler
from kanjilens.lookup import KanjiDB
from kanjilens.sentences import SentenceIndex
from kanjilens.sources import parse_jmdict
from kanjilens.builddb import build_database


def test_restricted_senses_are_not_shared_between_readings(tmp_path):
    xml = '''<JMdict><entry><k_ele><keb>生物</keb></k_ele>
      <r_ele><reb>なまもの</reb></r_ele><r_ele><reb>せいぶつ</reb></r_ele>
      <sense><stagr>なまもの</stagr><gloss>raw food</gloss></sense>
      <sense><stagr>せいぶつ</stagr><gloss>organism</gloss></sense>
      </entry><entry><k_ele><keb>犬</keb></k_ele><k_ele><keb>狗</keb></k_ele>
      <r_ele><reb>いぬ</reb></r_ele>
      <sense><stagk>犬</stagk><gloss>dog</gloss></sense>
      <sense><stagk>狗</stagk><gloss>archaic dog</gloss></sense></entry></JMdict>'''
    path = tmp_path / 'dictionary.gz'
    with gzip.open(path, 'wb') as f:
        f.write(xml.encode('utf-8'))
    words = {(w, r): g for w, r, g, *_ in parse_jmdict(path)}
    assert words['生物', 'なまもの'] == 'raw food'
    assert words['生物', 'せいぶつ'] == 'organism'
    assert words['犬', 'いぬ'] == 'dog'
    assert words['狗', 'いぬ'] == 'archaic dog'


def test_contextual_readings_reject_reported_errors():
    idx = SentenceIndex([
        (1, '理髪店に行って来たところだ。', 'I have been to the barber.'),
        (2, '食べ物は生物にとって必要なものです。', 'Food is necessary for life.'),
        (3, '会議を行います。', 'We will hold a meeting.'),
        (4, '赤ちゃんが生まれた。', 'A baby was born.'),
        (5, '彼女はそこへひとりで行った。', 'She went there by herself.'),
    ])
    assert idx.find('行う', 'おこなう') == [dict(id=3, jp='会議を行います。', en='We will hold a meeting.')]
    assert idx.find('生物', 'なまもの') == []
    assert [s['id'] for s in idx.find('生物', 'せいぶつ')] == [2]
    assert [s['id'] for s in idx.find('生まれる', 'うまれる')] == [4]


def test_api_and_static_routes(db_path):
    # Exercise the HTTP request parser and response writer without requiring
    # access to the host's networking stack.
    class Client:
        def __init__(self, path):
            self.input = BytesIO(f'GET {path} HTTP/1.0\r\n\r\n'.encode('ascii'))
            self.output = bytearray()

        def makefile(self, *args):
            return self.input

        def sendall(self, data):
            self.output.extend(data)

    def get(path):
        client = Client(path)
        make_handler(str(db_path))(client, ('127.0.0.1', 1), None)
        headers, body = bytes(client.output).split(b'\r\n\r\n', 1)
        return int(headers.split()[1]), body

    status, body = get('/api/lookup?q=%E7%8A%AC')
    assert status == 200
    data = json.loads(body)
    assert data['entries'][0]['literal'] == '犬'
    assert data['meta']['data_version'] == '2'
    for route in ['/', '/app.js', '/styles.css', '/photo.js', '/study.js']:
        status, body = get(route)
        assert status == 200 and body
    assert get('/api/lookup?q=' + 'a' * 201)[0] == 400
    assert get('/raw_data/JMdict_e.gz')[0] == 404


def test_lookup_skips_unknown_before_applying_limit(db_path):
    db = KanjiDB(str(db_path))
    try:
        assert [x['literal'] for x in db.get_many('鬱犬', limit=1)] == ['犬']
        assert db.get_many('犬', limit=0) == []
    finally:
        db.close()


def test_build_withholds_ambiguous_and_set_word_examples(raw, tmp_path):
    extra = '''<entry><k_ele><keb>生物</keb><ke_pri>ichi1</ke_pri></k_ele>
      <r_ele><reb>なまもの</reb><re_pri>ichi1</re_pri></r_ele>
      <r_ele><reb>せいぶつ</reb><re_pri>ichi1</re_pri></r_ele>
      <sense><stagr>なまもの</stagr><gloss>raw food</gloss></sense>
      <sense><stagr>せいぶつ</stagr><gloss>organisms</gloss></sense></entry>'''
    with gzip.open(raw / 'JMdict_e.gz', 'rt', encoding='utf-8') as f:
        xml = f.read().replace('</JMdict>', extra + '</JMdict>')
    jm = tmp_path / 'jm.gz'
    with gzip.open(jm, 'wb') as f:
        f.write(xml.encode('utf-8'))
    furi = tmp_path / 'furi.txt'
    furi.write_text((raw / 'JmdictFurigana.txt').read_text(encoding='utf-8-sig') +
                    '生物|なまもの|0:なま;1:もの\n生物|せいぶつ|0:せい;1:ぶつ\n', encoding='utf-8')
    out = tmp_path / 'out.db'
    build_database(str(out), raw / 'kanjidic2.xml.gz', jm, furi, lambda _: 5,
                   sentences=[(1, '食べ物は生物にとって必要なものです。', 'Food is necessary for life.'),
                              (2, '弥生のナビは難しい。', "Yayoi's navigation is difficult.")], log=lambda _: None)
    db = KanjiDB(str(out))
    try:
        words = [w for g in db.get('生')['groups'] for w in g['words']]
        targets = [w for w in words if w['word'] in {'生物', '弥生'}]
        assert len(targets) == 3
        assert all(not w['sentences'] for w in targets)
    finally:
        db.close()
