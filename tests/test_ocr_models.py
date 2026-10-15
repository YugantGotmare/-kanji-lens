"""Opt-in tests of the downloaded model, using the actual reported OCR failures."""
import os
from pathlib import Path

import pytest

from kanjilens.ocr import LocalOCR


@pytest.mark.skipif(os.environ.get('KANJILENS_TEST_OCR') != '1', reason='Set KANJILENS_TEST_OCR=1 in the OCR environment')
def test_reported_kanji_images():
    engine = LocalOCR()
    fixtures = Path(__file__).parent / 'fixtures' / 'ocr'
    for filename, expected in [('no.png', '野'), ('kuro.png', '黒'), ('line.png', '犬生行')]:
        result = engine.recognize((fixtures / filename).read_bytes())
        assert ''.join(result['text'].split()) == expected, result
