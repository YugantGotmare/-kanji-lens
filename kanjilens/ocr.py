"""Optional, local CPU OCR. Download models explicitly: python -m kanjilens.ocr --setup."""
import argparse
import io
import os
from pathlib import Path
import tarfile
import threading
import urllib.request

MODEL_ROOT = Path(__file__).resolve().parent.parent / '.ocr-models'
RECOGNIZER = 'PP-OCRv5_server_rec'
DETECTOR = 'PP-OCRv5_mobile_det'
MODEL_FILES = {'inference.json', 'inference.pdiparams', 'inference.yml'}
MAX_UPLOAD = 20 * 1024 * 1024


class OCRUnavailable(RuntimeError):
    pass


class OCRBusy(RuntimeError):
    pass


def model_ready(name):
    return all((MODEL_ROOT / name / filename).is_file() for filename in MODEL_FILES)


def download_models():
    MODEL_ROOT.mkdir(exist_ok=True)
    for name in (RECOGNIZER, DETECTOR):
        if model_ready(name):
            print(f'{name}: already downloaded', flush=True)
            continue
        url = f'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/{name}_infer.tar'
        archive = MODEL_ROOT / f'{name}.tar.part'
        print(f'Downloading {name} ...', flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as target:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
        directory = MODEL_ROOT / name
        directory.mkdir(exist_ok=True)
        # Copy only the three expected model files, never archive paths/links.
        with tarfile.open(archive) as package:
            for member in package:
                filename = Path(member.name).name
                if not member.isfile() or filename not in MODEL_FILES:
                    continue
                if member.size > 250 * 1024 * 1024:
                    raise ValueError('Unexpected model file size')
                source = package.extractfile(member)
                with source, (directory / (filename + '.part')).open('wb') as target:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                os.replace(directory / (filename + '.part'), directory / filename)
        if not model_ready(name):
            raise RuntimeError(f'Model archive is missing required files: {name}')
        archive.unlink()
        print(f'{name}: ready', flush=True)


class LocalOCR:
    def __init__(self):
        self.lock = threading.Lock()
        self.recognizer = None
        self.pipeline = None

    def _load(self, full_page):
        names = (RECOGNIZER, DETECTOR) if full_page else (RECOGNIZER,)
        if not all(model_ready(name) for name in names):
            raise OCRUnavailable('Local OCR models are missing. Run python -m kanjilens.ocr --setup in the OCR environment, then restart the app.')
        os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(MODEL_ROOT / 'cache'))
        os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
        try:
            from paddleocr import PaddleOCR, TextRecognition
        except ImportError as error:
            raise OCRUnavailable('Local OCR is not installed in this Python environment. Start the app using .venv-ocr/Scripts/python.exe.') from error
        options = dict(device='cpu', enable_mkldnn=False, cpu_threads=4)
        if full_page and self.pipeline is None:
            self.pipeline = PaddleOCR(
                text_detection_model_name=DETECTOR, text_detection_model_dir=str(MODEL_ROOT / DETECTOR),
                text_recognition_model_name=RECOGNIZER, text_recognition_model_dir=str(MODEL_ROOT / RECOGNIZER),
                use_doc_orientation_classify=False, use_doc_unwarping=False,
                use_textline_orientation=False, **options)
        elif not full_page and self.recognizer is None:
            self.recognizer = TextRecognition(model_name=RECOGNIZER, model_dir=str(MODEL_ROOT / RECOGNIZER), **options)

    def recognize(self, raw, layout='auto'):
        if not self.lock.acquire(blocking=False):
            raise OCRBusy('Another photo is being recognized. Please try again shortly.')
        try:
            try:
                import numpy as np
                from PIL import Image, ImageOps, UnidentifiedImageError
            except ImportError as error:
                raise OCRUnavailable('Install requirements-ocr.txt and start the app in the OCR environment.') from error
            if not raw or len(raw) > MAX_UPLOAD:
                raise ValueError('Choose an image smaller than 20 MB.')
            try:
                with Image.open(io.BytesIO(raw)) as source:
                    if source.width * source.height > 16_000_000:
                        raise ValueError('Image is too large. Crop it to fewer than 16 million pixels.')
                    source = ImageOps.exif_transpose(source).convert('RGBA')
                    image = Image.new('RGB', source.size, 'white')
                    image.paste(source, mask=source.getchannel('A'))
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
                raise ValueError('This file is not a supported image.') from error
            # A detector can split an isolated glyph into radicals. Recognize a
            # square crop directly; use detection for larger text scenes.
            full_page = layout not in {'10', 'line'} and (layout != 'auto' or image.width / image.height > 1.5 or image.height / image.width > 1.5)
            self._load(full_page)
            pixels = np.asarray(image)[:, :, ::-1].copy()  # Paddle expects BGR
            if full_page:
                result = list(self.pipeline.predict(pixels, text_rec_score_thresh=0.0))[0]
                lines = [{'text': str(t), 'confidence': float(s)}
                         for t, s in zip(result['rec_texts'], result['rec_scores']) if str(t).strip()]
                text = '\n'.join(line['text'] for line in lines)
                score = min((line['confidence'] for line in lines), default=0)
                alternatives = []
                if score < .85 and layout != '5':
                    # Very large, spaced glyphs can defeat text detection. Try
                    # the whole crop as a line, retaining disagreement visibly.
                    self._load(False)
                    retry = list(self.recognizer.predict(pixels))[0]
                    other_text, other_score = str(retry['rec_text']).strip(), float(retry['rec_score'])
                    if other_text and other_text != text:
                        if other_score > score:
                            if text:
                                alternatives.append({'text': text, 'confidence': score})
                            text, score = other_text, other_score
                        else:
                            alternatives.append({'text': other_text, 'confidence': other_score})
            else:
                predictions = list(self.recognizer.predict(pixels))
                result = predictions[0]
                text, score = str(result['rec_text']).strip(), float(result['rec_score'])
                alternatives = []
                if score < .9:
                    clean = ImageOps.grayscale(image).point(lambda value: 0 if value < 160 else 255).convert('RGB')
                    retry = list(self.recognizer.predict(np.asarray(clean)[:, :, ::-1].copy()))[0]
                    other = {'text': str(retry['rec_text']).strip(), 'confidence': float(retry['rec_score'])}
                    if other['text'] and other['text'] != text:
                        if other['confidence'] > score:
                            alternatives.append({'text': text, 'confidence': score})
                            text, score = other['text'], other['confidence']
                        else:
                            alternatives.append(other)
            return {'text': text[:2000], 'confidence': score, 'alternatives': alternatives,
                    'uncertain': score < .85 or bool(alternatives), 'engine': 'PaddleOCR / PP-OCRv5 (local CPU)'}
        finally:
            self.lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('images', nargs='*')
    args = parser.parse_args()
    if args.setup:
        download_models()
    if args.images:
        import json
        engine = LocalOCR()
        for image in args.images:
            result = engine.recognize(Path(image).read_bytes())
            print(json.dumps({'image': image, **result}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
