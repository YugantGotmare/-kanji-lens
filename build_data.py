"""Build kanji_lens.db from the raw dictionary sources. Run once, then ship the .db file with the app.

    pip install -r requirements-build.txt
    python build_data.py                    # downloads about 100 MB into raw_data/, writes kanji_lens.db
    python build_data.py --no-sentences     # skip example sentences (faster)
    python build_data.py --limit 50         # only the 50 most frequent kanji, for a quick test
"""
import argparse

from kanjilens.builddb import build_database, wordfreq_zipf
from kanjilens.sources import fetch, read_tatoeba


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="raw_data", help="where downloads are kept (default: raw_data)")
    ap.add_argument("--out", default="kanji_lens.db", help="database file to write")
    ap.add_argument("--no-sentences", action="store_true", help="skip Tatoeba example sentences")
    ap.add_argument("--limit", type=int, help="only build the N most frequent kanji")
    args = ap.parse_args()

    kd = fetch("kanjidic2.xml.gz", args.data_dir)
    jm = fetch("JMdict_e.gz", args.data_dir)
    furi = fetch("JmdictFurigana.txt", args.data_dir)

    sentences = None
    if not args.no_sentences:
        jpn = fetch("jpn_sentences.tsv.bz2", args.data_dir, required=False)
        eng = fetch("eng_sentences.tsv.bz2", args.data_dir, required=False)
        links = fetch("jpn-eng_links.tsv.bz2", args.data_dir, required=False)
        if jpn and eng and links:
            sentences = read_tatoeba(jpn, eng, links)
            print(f"{len(sentences)} Japanese sentences with English translations")
        else:
            print("Sentences disabled: Tatoeba download failed.")

    build_database(args.out, kd, jm, furi, wordfreq_zipf(), sentences=sentences, limit=args.limit)


if __name__ == "__main__":
    main()
