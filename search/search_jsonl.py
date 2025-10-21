# search_jsonl.py  (može i eval/search_jsonl.py)
import json
import re
import sys
from pathlib import Path

PATH = Path("data/processed/updates_paragraphs.jsonl")
TOKEN = re.compile(r"[A-Za-zÀ-ž0-9]+")


def norm(txt):
    return " ".join(TOKEN.findall((txt or "").lower()))


def score(hit_text, q_terms):
    # prosta skala: broj pojavljivanja termina (TF); možeš lako proširiti
    txt = norm(hit_text)
    return sum(txt.count(t) for t in q_terms)


def main():
    if not PATH.exists():
        print(f"Ne postoji {PATH}")
        sys.exit(1)
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("Upotreba: python search_jsonl.py <query>")
        sys.exit(1)
    q_terms = [t.lower() for t in TOKEN.findall(query)]
    results = []
    with PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            txt = " ".join([
                rec.get("title") or "",
                rec.get("section_title") or "",
                rec.get("subsection_title") or "",
                rec.get("text") or "",
            ])
            sc = score(txt, q_terms)
            if sc > 0:
                results.append((sc, rec))
    results.sort(key=lambda x: x[0], reverse=True)
    for sc, r in results[:10]:
        print(f"\n[score={sc}] {r.get('title')} | {r.get('url')}")
        print(f"→ {(r.get('text') or '')[:300]}")
    print(f"\nUkupno hitova: {len(results)}")


if __name__ == "__main__":
    main()
