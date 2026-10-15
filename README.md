# Kanji Lens

Learn common Japanese vocabulary from a kanji or a photo. Kanji Lens groups words
by reading and provides meanings, automatic example sentences, browser audio,
saved words, and spaced review in a local web app.

Photo recognition uses free local PaddleOCR, with an optional browser-based
Tesseract fallback. OCR and example sentences can make mistakes; the app shows
uncertain results for correction.

## Start from a fresh clone (Windows)

Install Python 3.12 (64-bit), open a terminal in the cloned repository, and run:

```powershell
python -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt -r requirements-build.txt
.\.venv-ocr\Scripts\python.exe build_data.py
.\.venv-ocr\Scripts\python.exe -m kanjilens.ocr --setup
.\.venv-ocr\Scripts\python.exe app.py
```

Open http://127.0.0.1:8000. Dictionary downloads, database generation, and OCR
model setup are needed once. These generated files are excluded from Git.
On macOS/Linux, replace `.\.venv-ocr\Scripts\python.exe` with
`.venv-ocr/bin/python`.

For tests and contribution guidance, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout
- `build_data.py` builds `kanji_lens.db` once from the raw sources (the slow part).
- `kanjilens/` is the library: `sources` (download and parse), `grouping` (reading groups and ranking),
  `sentences` (verified sentence index), `builddb` (writes the database), `lookup` (reads it; all the app needs).
- `tests/` runs offline on small synthetic copies of the real file formats.

## Use
    pip install -r requirements-build.txt
    python build_data.py                                  # about 100 MB download, then the build
    python -m kanjilens.lookup kanji_lens.db 犬           # try it
    pip install pytest && python -m pytest                # tests

## Local learning screen

For the free local PaddleOCR scanner, use the isolated OCR environment (Python 3.12,
64-bit recommended). Setup downloads the CPU framework and models once; no API key
or paid OCR service is used:

    python -m venv .venv-ocr
    .\.venv-ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt -r requirements-build.txt
    .\.venv-ocr\Scripts\python.exe -m kanjilens.ocr --setup
    .\.venv-ocr\Scripts\python.exe app.py

If you use an existing database, no rebuild is needed for this OCR change. The detector
and recognizer weights take about 89 MB together, in `.ocr-models/`; the Python CPU
framework and dependencies need additional disk space. Once setup is complete, local
recognition uses these files without downloading models during a scan. Keep the app
running in the OCR environment; launching it with a different Python may lack PaddleOCR.
Restart the server using the OCR environment command above after setup, then refresh
your browser to load the new default scanner.

The lightweight screen can also run without local OCR dependencies:

    python build_data.py
    python app.py

Open http://127.0.0.1:8000, enter a kanji (for example 生), and click Explore.
The screen shows vocabulary grouped by reading, kana above each word, English meanings,
example source links, and word/sentence playback. It runs locally with Python's standard
library; no web framework or paid speech API is required. Use `--port` or `--db` to change
the server port or database path.

### Photo lookup

Choose **Take a photo** on a supported phone, or **Choose image** to upload a picture.
Adjust the crop sliders to isolate the text; rotate if necessary. Start with Automatic
layout, or choose horizontal, vertical, or single-character layout, then click **Read kanji from image**. Check the
recognized text and tap any detected kanji to open its vocabulary, examples, and audio.
Text can be corrected before lookup. You can cancel a scan and retry.

The default scanner uses [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) on the
computer running the Python app. The selected crop is sent to this local server,
decoded in memory, and is not saved or sent to a cloud OCR service. Isolated/square
character crops use the recognition model directly; text scenes use detection followed
by recognition. Low-confidence character crops get a second black-and-white recognition
attempt; disagreement is shown rather than treated as verified. Confidence is a model
score, not a guarantee of correctness. Use Single character for a tight glyph crop,
Single line for a cropped phrase, and Horizontal/Vertical for text scenes.

You can explicitly choose **Tesseract · browser fallback** instead. It uses
[Tesseract.js](https://github.com/naptha/tesseract.js), pinned to version 6.0.1, inside
your browser. The first fallback scan needs internet to download its engine and Japanese
model; images in this mode are not sent to the Python server. Vertical fallback uses
the Japanese vertical model. Clear printed text works best; handwriting,
blur, unusual fonts, and low-resolution photos may need manual correction. Images are
limited to 20 MB and resized to at most 2,400 pixels on their longest side.
Browser fallback adds a white margin around tight crops. If the result contains no kanji
or has low confidence, non-vertical scans retry with a clean black-and-white background
and alternative segmentation. This helps large isolated glyphs and pale checkerboard
backgrounds. Uncertain results are labeled for correction; OCR is not guaranteed.

To use the app on your phone while Python runs on your computer, run:

    .\.venv-ocr\Scripts\python.exe app.py --host 0.0.0.0

Connect both devices to the same trusted network, then open
`http://YOUR-COMPUTER-LAN-IP:8000` on the phone. Allow the port through your computer's
firewall if required. This is a local development server, without accounts or authentication.

### Saved words and review

Click **Save word** on any vocabulary card. **Saved words** lists your collection;
**Review** offers due words with a hidden answer. Reveal the reading and meaning,
listen, then choose practice again (10 minutes) or remembered (1 day initially,
doubling after each success, up to 365 days).

Words and progress are kept in this browser's local storage, separately for each
site address/device. **Export backup** downloads a JSON file; **Import backup** merges
a backup without replacing existing words or progress. Export before clearing browser
data or changing computers. Different readings of the same spelling are saved separately.

Run the additional study-logic tests with `node --test tests/study.test.cjs` (Node.js).
To run the actual model regressions on the supplied 野 and 黒 screenshots (after setup):

    $env:KANJILENS_TEST_OCR = '1'
    .\.venv-ocr\Scripts\python.exe -m pytest tests/test_ocr_models.py -q

The fixtures cover the two reported failures and one generated line of text, not general
accuracy across fonts or camera photos. To inspect other images locally:

    .\.venv-ocr\Scripts\python.exe -X utf8 -m kanjilens.ocr path\to\image.png

Cancel stops the browser from waiting for a result. A local inference already running
may finish on the server; another scan gets a busy message until it completes.

Audio uses the browser's Japanese voices. If no Japanese voice is available, playback
is disabled with an explanation. Enable a Japanese voice on your device or try another
browser. Word audio uses kana to avoid ambiguous kanji readings. Sentence audio is
synthetic and its readings and pitch accent have not been reviewed; voice availability
and offline behavior depend on the browser and selected voice.

## Accuracy and rebuilds

Rebuild old databases with `python build_data.py`; the learning screen requires data
version 2 to avoid serving known incorrect examples. Downloads already in `raw_data/`
are reused. The CLI can still read older databases.

Dictionary glosses respect spelling and reading restrictions. Sentence matching uses
orthographic dictionary readings (`kanaBase`) and actual token readings (`kana`),
rather than lemma readings (`lForm`). Inflected forms remain supported, except
ambiguous contracted -tta/-tte lemma matches, which are withheld. Recognized
proper names are excluded. Automatic examples are withheld for spellings with distinct
dictionary glosses and for set-word groups, where reading/sense ambiguity needs review.
This conservative policy reduces coverage; it does not establish that every remaining
sentence illustrates the intended meaning. Examples are explicitly labeled automatic,
not human-reviewed. Whole-word kana is displayed as ruby; sentence furigana, reviewed
example curation, recorded/validated audio, and workplace categories
remain future work.

## Data and licences (credit is required, keep these visible in the app)
- KANJIDIC2 and JMdict: EDRDG, CC BY-SA 4.0. The built database is derived from them, so it must be
  shared under CC BY-SA 4.0 as well.
- JmdictFurigana: Doublevil, https://github.com/Doublevil/JmdictFurigana (check its licence before launch).
- Tatoeba sentences: CC BY 2.0 FR, https://tatoeba.org. Every stored sentence keeps its Tatoeba id so it can be
  linked back to its page and author.
- Word frequencies: wordfreq (Robyn Speer), check its data licence before launch.
