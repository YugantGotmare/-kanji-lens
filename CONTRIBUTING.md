# Contributing

Use Python 3.12 and install development dependencies in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/study.test.cjs
```

Node.js 22 is used in CI for the browser-independent study logic tests. On macOS
or Linux, use `.venv/bin/python` instead of the Windows interpreter path.

The regular test suite uses small fixtures and does not need downloaded
dictionaries, a generated database, or OCR model weights. Real OCR regressions
are opt-in; see the README for setup and the test command.

Keep changes focused, describe the user-visible behavior, and include the
validation performed in pull requests. Do not commit virtual environments,
downloaded datasets, model weights, generated databases, or credentials.

Dictionary, sentence, and model sources retain their own licenses. Preserve
source credits when changing data processing or displaying learning content.
