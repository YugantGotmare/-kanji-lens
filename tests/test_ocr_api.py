import json
from io import BytesIO

import pytest

from app import make_handler
from kanjilens.ocr import MAX_UPLOAD, OCRBusy, OCRUnavailable


def request(engine, body=b'fake image', headers=None, path='/api/ocr?layout=10'):
    class Client:
        def __init__(self):
            fields = {'Content-Type': 'image/png', 'Content-Length': str(len(body)), **(headers or {})}
            prefix = 'POST ' + path + ' HTTP/1.0\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in fields.items()) + '\r\n'
            self.input = BytesIO(prefix.encode('ascii') + body)
            self.output = bytearray()

        def makefile(self, *args):
            return self.input

        def sendall(self, data):
            self.output.extend(data)
    client = Client()
    make_handler('unused.db', engine)(client, ('127.0.0.1', 1), None)
    headers, payload = bytes(client.output).split(b'\r\n\r\n', 1)
    return int(headers.split()[1]), json.loads(payload)


def test_ocr_api_preserves_characters_and_uncertainty():
    class Engine:
        def recognize(self, raw, layout):
            assert raw == b'fake image' and layout == '10'
            return {'text': '黒', 'confidence': .7, 'uncertain': True,
                    'alternatives': [{'text': '墨', 'confidence': .6}]}
    status, data = request(Engine())
    assert status == 200 and data['text'] == '黒'
    assert data['uncertain'] is True and data['alternatives'][0]['text'] == '墨'


@pytest.mark.parametrize(('error', 'status'), [(OCRUnavailable('setup needed'), 503),
    (OCRBusy('busy'), 429), (ValueError('bad image'), 400)])
def test_ocr_api_returns_actionable_errors(error, status):
    class Engine:
        def recognize(self, *_):
            raise error
    actual, data = request(Engine())
    assert actual == status and data['error'] == str(error)


def test_ocr_api_validates_requests_before_calling_engine():
    class Engine:
        def recognize(self, *_):
            pytest.fail('Invalid input reached the recognizer')
    engine = Engine()
    assert request(engine, headers={'Content-Length': str(MAX_UPLOAD + 1)})[0] == 413
    assert request(engine, headers={'Content-Length': 'invalid'})[0] == 413
    assert request(engine, headers={'Content-Type': 'text/plain'})[0] == 415
    assert request(engine, path='/api/ocr?layout=unknown')[0] == 400
    assert request(engine, headers={'Origin': 'https://other.example', 'Host': 'localhost:8000'})[0] == 403
    assert request(engine, path='/unknown')[0] == 404
