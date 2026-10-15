"""Run the local Kanji Lens learning screen: python app.py."""
import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from kanjilens.lookup import KanjiDB
from kanjilens.ocr import LocalOCR, MAX_UPLOAD, OCRBusy, OCRUnavailable

STATIC = Path(__file__).resolve().parent / "static"


def make_handler(database, ocr=None):
    engine = ocr if ocr is not None else LocalOCR()
    class Handler(BaseHTTPRequestHandler):
        def json_response(self, status, payload):
            self.respond(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

        def respond(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != '/api/ocr':
                self.json_response(404, {'error': 'Not found'})
                return
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                self.json_response(403, {'error': 'Open the scanner from this app.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] not in {'image/png', 'image/jpeg', 'image/webp'}:
                self.json_response(415, {'error': 'Send a PNG, JPEG, or WebP image.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            if size <= 0 or size > MAX_UPLOAD:
                self.json_response(413, {'error': 'Choose an image smaller than 20 MB.'})
                return
            layout = parse_qs(url.query).get('layout', ['auto'])[0]
            if layout not in {'auto', '6', '5', '10', 'line'}:
                self.json_response(400, {'error': 'Unsupported text layout.'})
                return
            try:
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('The image upload was incomplete.')
                result = engine.recognize(raw, layout)
                self.json_response(200, result)
            except ValueError as error:
                self.json_response(400, {'error': str(error)})
            except OCRUnavailable as error:
                self.json_response(503, {'error': str(error)})
            except OCRBusy as error:
                self.json_response(429, {'error': str(error)})
            except (BrokenPipeError, ConnectionResetError):
                return  # The browser cancelled; do not retain or retry its photo.
            except Exception:
                logging.exception('Local OCR failed')
                self.json_response(500, {'error': 'Local OCR could not run. Check the server terminal for details, or explicitly select browser OCR.'})

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/api/lookup":
                text = parse_qs(url.query).get("q", [""])[0]
                if len(text) > 200:
                    self.respond(400, b'{"error":"Enter at most 200 characters."}', "application/json")
                    return
                db = KanjiDB(database)
                try:
                    meta = db.meta()
                    if meta.get("data_version") != "2":
                        self.respond(409, json.dumps({"error": "Rebuild the database with python build_data.py before using this screen."}).encode(), "application/json")
                        return
                    payload = {"entries": db.get_many(text), "meta": meta}
                finally:
                    db.close()
                self.respond(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                      "/photo.js": ("photo.js", "text/javascript"), "/study.js": ("study.js", "text/javascript"),
                      "/styles.css": ("styles.css", "text/css")}
            if url.path not in assets:
                self.respond(404, b"Not found", "text/plain")
                return
            name, kind = assets[url.path]
            self.respond(200, (STATIC / name).read_bytes(), kind + "; charset=utf-8")
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="kanji_lens.db")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address; use 0.0.0.0 to access from your phone on the same network")
    args = parser.parse_args()
    db = KanjiDB(args.db)
    db.meta()
    db.close()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.db))
    print(f"Kanji Lens listening on {args.host}:{args.port}")
    print(f"On this computer: http://127.0.0.1:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
